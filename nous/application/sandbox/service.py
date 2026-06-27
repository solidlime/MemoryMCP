from __future__ import annotations

import asyncio
import contextlib
import json as _json
import logging
import os
import uuid
from dataclasses import dataclass, field

import docker
from docker.errors import NotFound

from nous.application.sandbox.user_manager import (
    SANDBOX_CONTAINER_NAME,
    make_username,
    user_create_commands,
    user_delete_commands,
    user_exists_commands,
)

logger = logging.getLogger(__name__)

WORKSPACE = "/sandbox"
UPLOADS_DIR = f"{WORKSPACE}/uploads"
OUTPUT_DIR = f"{WORKSPACE}/output"


@dataclass
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    artifacts: list[str] = field(default_factory=list)  # base64-encoded PNG strings
    language: str = "python"


@dataclass
class SandboxFileInfo:
    name: str
    path: str
    is_dir: bool
    size: int = 0


_LANG_ROUTING: dict[str, tuple[str, str]] = {
    "python": ("python3", ".py"),
    "py": ("python3", ".py"),
    "javascript": ("node", ".js"),
    "js": ("node", ".js"),
    "node": ("node", ".js"),
    "bash": ("bash", ".sh"),
    "sh": ("bash", ".sh"),
    "shell": ("bash", ".sh"),
    "go": ("go run", ".go"),
    "golang": ("go run", ".go"),
    "rust": ("rustc {file} -o {bin} && {bin}", ".rs"),
    "rs": ("rustc {file} -o {bin} && {bin}", ".rs"),
}


class SandboxSession:
    """Single sandbox container execution via docker exec.

    No longer per-persona container. All personas share the same container,
    isolated by Linux user accounts.
    """

    def __init__(self, persona: str) -> None:
        self.persona = persona
        self.username = persona  # username = persona name, no prefix
        self._docker: docker.DockerClient | None = None
        self._container = None
        self._last_access: float | None = None
        self._initialized = False

    async def _ensure_container(self) -> None:
        """Ensure sandbox container is running."""
        if self._container is not None:
            return
        if self._docker is None:
            self._docker = docker.from_env()
        try:
            self._container = self._docker.containers.get(SANDBOX_CONTAINER_NAME)
            if self._container.status != "running":
                self._container.start()
            logger.debug("Sandbox container %s is %s", SANDBOX_CONTAINER_NAME, self._container.status)
        except NotFound:
            raise RuntimeError(
                f"Sandbox container '{SANDBOX_CONTAINER_NAME}' not found. "
                "Run: docker compose up -d sandbox"
            ) from None

    async def _ensure_user(self) -> None:
        """Create Linux user for this persona if not exists (idempotent)."""
        if self._initialized:
            return
        await self._ensure_container()
        cmds = user_create_commands(self.persona)
        script = " && ".join(cmds)
        stdout, stderr, exit_code = await self._exec_root(f"bash -c {_safe_quote(script)}")
        if exit_code != 0:
            logger.warning("User creation had issues for %s: %s", self.persona, stderr)
        self._initialized = True
        logger.info("Sandbox user ensured: %s", self.username)

    def _build_env(self) -> dict[str, str]:
        """Build environment for persona user execution.

        LLM never needs to know these values -- they are injected automatically.
        """
        home = f"/home/{self.username}"
        return {
            "HOME": home,
            "USER": self.username,
            "LOGNAME": self.username,
            "PATH": (
                f"{home}/.local/bin:{home}/.cargo/bin:{home}/.npm-global/bin"
                ":/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            ),
            "PIP_USER": "1",
            "SANDBOX_WORKDIR": home,
            "SANDBOX_PERSONA": self.persona,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }

    async def _exec_root(self, cmd: str, workdir: str = WORKSPACE, timeout: int = 60) -> tuple[str, str, int]:
        """Execute command as root in sandbox container."""
        await self._ensure_container()
        wrapped = ["bash", "-c", f"cd {workdir} && {cmd}"]
        try:
            exit_code, output = await asyncio.to_thread(
                self._container.exec_run,
                wrapped,
                user="root",
                demux=True,
            )
            stdout_bytes, stderr_bytes = output if isinstance(output, tuple) else (output, None)
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            return stdout, stderr, exit_code
        except Exception as e:
            logger.error("exec_root failed: %s", e)
            return "", str(e), 1

    async def _exec_user(self, cmd: str, workdir: str | None = None, timeout: int = 60) -> tuple[str, str, int]:
        """Execute command as persona user. Automatically sets HOME, USER, PATH, PIP_USER.

        Args:
            cmd: Shell command to execute
            workdir: Working directory (defaults to persona home)
        """
        await self._ensure_container()
        if workdir is None:
            workdir = f"/home/{self.username}"

        wrapped = ["bash", "-c", f"cd {workdir} && {cmd}"]
        env = self._build_env()
        try:
            exit_code, output = await asyncio.to_thread(
                self._container.exec_run,
                wrapped,
                user=self.username,
                environment=env,
                demux=True,
            )
            stdout_bytes, stderr_bytes = output if isinstance(output, tuple) else (output, None)
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            return stdout, stderr, exit_code
        except Exception as e:
            logger.error("exec_user failed for %s: %s", self.username, e)
            return "", str(e), 1

    async def _execute_via_file(self, code: str, run_cmd_template: str, ext: str, language: str) -> ExecResult:
        """Safe execution: write code to temp file, run, cleanup.

        Shell escaping is avoided by writing code to a heredoc file first.
        """
        filepath = f"/home/{self.username}/._sandbox_{uuid.uuid4().hex[:8]}{ext}"
        binpath = f"{filepath}.bin"

        # Write code via heredoc (safe -- no shell escaping needed)
        stdout, stderr, exit_code = await self._exec_root(
            f"cat > {filepath} << 'SANDBOX_END'\n{code}\nSANDBOX_END"
        )
        if exit_code != 0:
            return ExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code, language=language)

        # Fix ownership
        await self._exec_root(f"chown {self.username}:{self.username} {filepath}")

        # Execute via run command
        run_cmd = run_cmd_template.format(file=filepath, bin=binpath)
        stdout, stderr, exit_code = await self._exec_user(run_cmd, workdir=f"/home/{self.username}")

        # Cleanup
        await self._exec_root(f"rm -f {filepath} {binpath} 2>/dev/null")

        return ExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code, language=language)

    async def execute(self, code: str, language: str = "python", libraries: list[str] | None = None) -> ExecResult:
        """Execute code in sandbox as the persona user."""
        await self._ensure_user()
        self._last_access = asyncio.get_event_loop().time()

        # Install libraries if specified
        if libraries:
            await self.install_packages(libraries)

        # Route by language
        lang_key = language.lower()
        if lang_key in _LANG_ROUTING:
            run_cmd, ext = _LANG_ROUTING[lang_key]
            return await self._execute_via_file(code, run_cmd, ext, language)

        return ExecResult(stderr=f"Unsupported language: {language}", exit_code=1, language=language)

    async def install_packages(self, packages: list[str]) -> str:
        """Install Python packages as persona user (pip install --user)."""
        await self._ensure_user()
        cmd = f"python3 -m pip install --user {' '.join(packages)}"
        stdout, stderr, exit_code = await self._exec_user(cmd)
        if exit_code != 0:
            logger.warning("pip install failed for %s: %s", self.persona, stderr)
            return stderr
        return stdout

    # ---- File Operations ----

    async def read_file_text(self, remote_path: str) -> str:
        """Read a text file from sandbox container (as persona user)."""
        stdout, stderr, exit_code = await self._exec_user(f"cat {remote_path}")
        if exit_code != 0:
            raise FileNotFoundError(stderr or f"File not found: {remote_path}")
        return stdout

    async def write_file_text(self, remote_path: str, content: str) -> None:
        """Write text to sandbox container via heredoc (as root, then chown)."""
        dirpath = os.path.dirname(remote_path)
        if dirpath:
            await self._exec_root(f"mkdir -p {dirpath} && chown {self.username}:{self.username} {dirpath}")

        # Write via heredoc for safety
        filepath = remote_path
        stdout, stderr, exit_code = await self._exec_root(
            f"cat > {filepath} << 'SANDBOX_END'\n{content}\nSANDBOX_END"
        )
        if exit_code != 0:
            raise OSError(stderr or f"Failed to write: {filepath}")

        # Fix ownership
        await self._exec_root(f"chown {self.username}:{self.username} {filepath}")

    async def list_files(self, path: str = WORKSPACE) -> list[SandboxFileInfo]:
        """List files in sandbox directory (as persona user)."""
        code = (
            "import os, json, stat\n"
            f"entries = []\n"
            f"for entry in os.scandir({path!r}):\n"
            "    try:\n"
            "        st = entry.stat()\n"
            "        entries.append({'name': entry.name, 'path': entry.path, 'is_dir': entry.is_dir(), 'size': st.st_size})\n"
            "    except OSError:\n"
            "        entries.append({'name': entry.name, 'path': entry.path, 'is_dir': entry.is_dir(), 'size': 0})\n"
            "print(json.dumps(entries))"
        )
        stdout, stderr, exit_code = await self._exec_user(
            f"python3 -c {_safe_quote(code)}"
        )
        if exit_code != 0:
            logger.warning("list_files failed for %s: %s", path, stderr)
            return []
        try:
            raw = _json.loads(stdout)
        except Exception:
            return []
        return [SandboxFileInfo(name=e["name"], path=e["path"], is_dir=e["is_dir"], size=e["size"]) for e in raw]

    async def read_file(self, remote_path: str) -> bytes:
        """Read binary file from sandbox container (as root for arbitrary file access)."""
        import base64

        code = (
            "import base64, sys\n"
            f"with open({remote_path!r}, 'rb') as f:\n"
            "    data = f.read()\n"
            "print(base64.b64encode(data).decode())\n"
        )
        stdout, stderr, exit_code = await self._exec_user(
            f"python3 -c {_safe_quote(code)}"
        )
        if exit_code != 0:
            raise FileNotFoundError(stderr or f"File not found: {remote_path}")
        return base64.b64decode(stdout.strip())

    async def delete_file(self, remote_path: str) -> bool:
        """Delete a file from sandbox container (as persona user)."""
        stdout, stderr, exit_code = await self._exec_user(f"rm -f {remote_path}")
        return exit_code == 0

    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file from local filesystem to sandbox container."""
        try:
            with open(local_path, "rb") as f:
                content = f.read()
            await self.write_file_text(remote_path, content.decode("utf-8", errors="replace"))
            return True
        except Exception as e:
            logger.error("upload_file failed: %s", e)
            return False

    async def read_image(self, remote_path: str) -> dict:
        """Read image file from sandbox with optional resize.

        Returns dict with content_base64, content_type, size, and optional resized info.
        """
        import base64

        try:
            data = await self.read_file(remote_path)
        except FileNotFoundError:
            raise

        # Detect content type
        content_type = "application/octet-stream"
        if data[:4] == b"\x89PNG":
            content_type = "image/png"
        elif data[:2] == b"\xff\xd8":
            content_type = "image/jpeg"
        elif data[:3] == b"GIF":
            content_type = "image/gif"
        elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            content_type = "image/webp"

        result: dict = {
            "content_base64": base64.b64encode(data).decode("ascii"),
            "content_type": content_type,
            "size": len(data),
        }

        # Resize if needed (max 1568px on longest side) -- run resize locally
        try:
            from io import BytesIO  # noqa: I001
            from PIL import Image

            img = Image.open(BytesIO(data))
            max_dim = 1568
            if max(img.size) > max_dim:
                orig_w, orig_h = img.size
                ratio = max_dim / max(img.size)
                new_size = (int(orig_w * ratio), int(orig_h * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                buf = BytesIO()
                img_format = "PNG" if content_type == "image/png" else "JPEG"
                img.save(buf, format=img_format)
                result["content_base64"] = base64.b64encode(buf.getvalue()).decode("ascii")
                result["size"] = buf.tell()
                result["resized"] = True
                result["orig_dims"] = f"{orig_w}x{orig_h}"
        except Exception:
            pass  # Resize is best-effort

        return result

    async def get_file_tree(self, path: str = WORKSPACE, max_depth: int = 3) -> str:
        """Get a tree-like listing of sandbox files (as persona user)."""
        code = (
            "import os\n"
            f"def _tree(p, depth=0, prefix=''):\n"
            "    if depth > {max_depth}: return []\n"
            "    lines = []\n"
            "    try:\n"
            "        entries = sorted(os.scandir(p), key=lambda e: (not e.is_dir(), e.name))\n"
            "    except PermissionError:\n"
            "        return [f'{prefix}[permission denied]']\n"
            "    for i, entry in enumerate(entries):\n"
            "        is_last = i == len(entries) - 1\n"
            "        connector = '\u2514\u2500\u2500 ' if is_last else '\u251c\u2500\u2500 '\n"
            "        lines.append(f'{prefix}{connector}{entry.name}')\n"
            "        if entry.is_dir():\n"
            "            ext_prefix = '    ' if is_last else '\u2502   '\n"
            "            lines.extend(_tree(entry.path, depth+1, prefix+ext_prefix))\n"
            "    return lines\n"
            f"for line in _tree({path!r}):\n"
            "    print(line)"
        )
        stdout, stderr, exit_code = await self._exec_user(
            f"python3 -c {_safe_quote(code)}"
        )
        return stdout if exit_code == 0 else stderr

    # ---- Reset / Context ----

    async def reset(self, level: str = "files") -> str:
        """Reset sandbox environment.

        level:
          - "files": Delete all files in home directory (keeps packages)
          - "packages": Also remove pip/npm/cargo packages
          - "full": Delete and recreate the Linux user
        """
        await self._ensure_user()
        home = f"/home/{self.username}"

        if level == "files":
            await self._exec_root(
                f"find {home} -type f "
                f"! -path '{home}/.local/*' "
                f"! -path '{home}/.cargo/*' "
                f"! -path '{home}/.npm-global/*' "
                f"! -path '{home}/.cache/*' "
                f"! -path '{home}/.config/*' "
                f"! -name '.bashrc' "
                f"-delete 2>/dev/null"
            )
            await self._exec_root(
                f"find {home} -type d -empty -delete 2>/dev/null"
            )
            await self._exec_root(f"mkdir -p {home}")
            return f"Sandbox files reset for {self.persona}"

        elif level == "packages":
            cmds = [
                f"rm -rf {home}/.local/lib/python*/site-packages/* 2>/dev/null",
                f"rm -rf {home}/.npm-global/lib/node_modules/* 2>/dev/null",
                f"rm -rf {home}/.cargo/registry/* 2>/dev/null",
            ]
            await self._exec_root(" && ".join(cmds))
            return f"Sandbox packages reset for {self.persona}"

        elif level == "full":
            await self._exec_root(
                f"id -u {self.username} &>/dev/null && userdel -r {self.username} || true"
            )
            self._initialized = False
            await self._ensure_user()
            return f"Sandbox fully reset for {self.persona} (user recreated)"

        return f"Unknown reset level: {level}"

    async def get_context(self) -> dict:
        """Get current sandbox environment info for LLM awareness."""
        await self._ensure_user()

        langs = {}
        checks: list[tuple[str, str]] = [
            ("python3", "--version"),
            ("node", "--version"),
            ("go", "version"),
            ("rustc", "--version"),
            ("bash", "--version"),
        ]
        for lang, check_cmd in checks:
            stdout, _, exit_code = await self._exec_user(f"{lang} {check_cmd}")
            if exit_code == 0 and stdout.strip():
                langs[lang] = stdout.strip().split("\n")[0]

        # Check pip packages
        pkgs: list[str] = []
        stdout, _, exit_code = await self._exec_user(
            "pip3 list --user --format=json 2>/dev/null || echo '[]'"
        )
        if exit_code == 0:
            try:  # noqa: SIM105
                pkgs = [p["name"] for p in _json.loads(stdout)]
            except Exception:
                pass

        return {
            "user": self.username,
            "home": f"/home/{self.username}",
            "languages": langs,
            "pip_packages": pkgs,
            "available_languages": list(_LANG_ROUTING.keys()),
        }

    async def close(self) -> None:
        """Release Docker client connection. Container stays running for other personas."""
        if self._docker:
            try:  # noqa: SIM105
                self._docker.close()
            except Exception:
                pass
            self._docker = None
        self._container = None
        self._initialized = False


# ---- Helper ----

def _safe_quote(s: str) -> str:
    """Safely quote a string for use in shell commands (single quotes)."""
    escaped = s.replace("'", "'\"'\"'")
    return f"'{escaped}'"


# ---- Standalone container operations ----

async def _get_container() -> tuple[docker.DockerClient, object]:
    """Get a running sandbox container (helper for standalone functions).

    Returns (client, container) tuple. Caller must close client.
    """
    client = docker.from_env()
    try:
        container = client.containers.get(SANDBOX_CONTAINER_NAME)
        if container.status != "running":
            container.start()
        return client, container
    except NotFound:
        client.close()
        raise RuntimeError(
            f"Sandbox container '{SANDBOX_CONTAINER_NAME}' not found. "
            "Run: docker compose up -d sandbox"
        ) from None


async def ensure_sandbox_user(persona: str) -> str:
    """Ensure Linux user exists in sandbox container. Returns username."""
    username = make_username(persona)
    client, container = await _get_container()
    try:
        # Check if user already exists
        check_cmd = user_exists_commands(persona)[0]
        exit_code, output = await asyncio.to_thread(
            container.exec_run, ["bash", "-c", check_cmd], user="root"
        )
        if exit_code == 0:
            logger.debug("Sandbox user already exists: %s", username)
            return username

        # Create user
        cmds = user_create_commands(persona)
        script = " && ".join(cmds)
        exit_code, output = await asyncio.to_thread(
            container.exec_run, ["bash", "-c", script], user="root", demux=True,
        )
        if exit_code != 0:
            _, stderr_bytes = output if isinstance(output, tuple) else (output, None)
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            logger.warning("User creation had issues for %s: %s", persona, stderr)
        logger.info("Sandbox user ensured: %s", username)
        return username
    finally:
        with contextlib.suppress(Exception):
            client.close()


async def delete_sandbox_user(persona: str) -> bool:
    """Delete Linux user from sandbox container. Returns True if deleted."""
    client, container = await _get_container()
    try:
        cmds = user_delete_commands(persona)
        exit_code, output = await asyncio.to_thread(
            container.exec_run, ["bash", "-c", cmds[0]], user="root",
        )
        if exit_code == 0:
            logger.info("Sandbox user deleted: %s", make_username(persona))
        else:
            logger.warning("Sandbox user deletion failed for %s", persona)
        return exit_code == 0
    finally:
        with contextlib.suppress(Exception):
            client.close()


# ---- Global session registry ----

_sessions: dict[str, SandboxSession] = {}


async def get_sandbox_session(persona: str) -> SandboxSession:
    """Get or create a sandbox session for the given persona.

    Ensures the Linux user exists in the sandbox container before creating
    a new session.
    """
    if persona not in _sessions:
        await ensure_sandbox_user(persona)
        _sessions[persona] = SandboxSession(persona)
        logger.info("Sandbox session created for persona=%s", persona)
    return _sessions[persona]


async def close_sandbox_session(persona: str) -> None:
    """Close and remove a sandbox session for the given persona."""
    session = _sessions.pop(persona, None)
    if session:
        await session.close()
        logger.info("Sandbox session closed for persona=%s", persona)
