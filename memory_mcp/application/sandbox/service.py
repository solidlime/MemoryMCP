from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = "/sandbox"
UPLOADS_DIR = f"{WORKSPACE}/uploads"
OUTPUT_DIR = f"{WORKSPACE}/output"

# Common Unix socket paths in priority order per OS
_SOCKET_CANDIDATES: dict[str, list[str]] = {
    "Linux": ["/var/run/docker.sock", "/run/docker.sock"],
    "Darwin": [
        os.path.expanduser("~/.docker/run/docker.sock"),
        "/var/run/docker.sock",
    ],
}


def _resolve_docker_host(explicit_host: str, docker_sock_override: str) -> str:
    """Return the DOCKER_HOST value to use, or empty string to keep current env."""
    if explicit_host:
        return explicit_host

    if platform.system() == "Windows":
        return "npipe:////./pipe/docker_engine"

    candidates: list[str] = []
    if docker_sock_override:
        candidates.append(docker_sock_override)
    candidates.extend(_SOCKET_CANDIDATES.get(platform.system(), ["/var/run/docker.sock"]))

    for path in candidates:
        if os.path.exists(path):
            return f"unix://{path}"

    return ""


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


_HOST_DATA_ROOT_CACHE: str | None = None
_HOST_DATA_ROOT_DETECTED = False


def _get_own_container_id() -> str | None:
    """Extract Docker container ID from /proc/self/cgroup (Linux only)."""
    for proc_file in ("/proc/self/cgroup", "/proc/self/mountinfo"):
        try:
            with open(proc_file) as f:
                for line in f:
                    m = re.search(r"[/-]([a-f0-9]{64})", line)
                    if m:
                        return m.group(1)
        except OSError:
            pass
    return None


def _auto_detect_host_data_root(data_root: str) -> str:
    """Auto-detect the Docker-host-side path of data_root by inspecting own container mounts.

    Returns empty string if not running in Docker or detection fails.
    Result is cached after first call.
    """
    global _HOST_DATA_ROOT_CACHE, _HOST_DATA_ROOT_DETECTED
    if _HOST_DATA_ROOT_DETECTED:
        return _HOST_DATA_ROOT_CACHE or ""
    _HOST_DATA_ROOT_DETECTED = True

    # Only relevant inside a Docker container
    if not os.path.exists("/.dockerenv"):
        return ""

    container_id = _get_own_container_id()
    if not container_id:
        return ""

    try:
        import docker

        client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
        container = client.containers.get(container_id)
        data_root_abs = str(Path(data_root).resolve())

        for mount in container.attrs.get("Mounts", []):
            dest = mount.get("Destination", "").rstrip("/")
            source = mount.get("Source", "").rstrip("/")
            if not dest or not source:
                continue
            if data_root_abs == dest or data_root_abs.startswith(dest + "/"):
                suffix = data_root_abs[len(dest) :].lstrip("/")
                host_path = f"{source}/{suffix}" if suffix else source
                logger.info("Auto-detected host data root: %s (from container mount %s -> %s)", host_path, source, dest)
                _HOST_DATA_ROOT_CACHE = host_path
                return host_path
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Host data root auto-detection failed: %s. "
            "Set MEMORY_MCP_SANDBOX__HOST_DATA_ROOT to the host-side path of '%s' "
            "(e.g. /volume1/docker/MemoryMCP/data) to enable sandbox file persistence.",
            exc,
            data_root,
        )

    return ""


def _verify_sandbox_mounts(session: object, container_configs: dict, persona: str) -> None:
    """Verify that the Docker volume mounts were applied to the sandbox container.

    Uses ``docker inspect`` via subprocess (no Python Docker SDK required).
    Logs a warning if volumes specified in container_configs are missing from the
    running container.
    """
    try:
        container_id = None
        for attr in ("container_id", "_container_id"):
            cid = getattr(session, attr, None)
            if cid:
                container_id = cid
                break
        if not container_id:
            for attr in ("container", "_container"):
                c = getattr(session, attr, None)
                if c is not None:
                    container_id = getattr(c, "id", None) or getattr(c, "short_id", None)
                    if container_id:
                        break
        if not container_id:
            logger.debug("Cannot verify sandbox mounts: no container_id found on session")
            return

        import json as _json
        import subprocess as _sp

        result = _sp.run(
            ["docker", "inspect", container_id],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.debug("docker inspect failed: %s", result.stderr.strip())
            return

        data = _json.loads(result.stdout)
        mounts = data[0].get("Mounts", []) if data else []
        expected_volumes = container_configs.get("volumes", {})

        if not mounts and expected_volumes:
            logger.warning(
                "Sandbox container %s has NO volume mounts! Expected: %s. "
                "Files written to /sandbox will NOT persist on host. "
                "llm_sandbox may not be applying container_configs['volumes'].",
                container_id[:12],
                list(expected_volumes.keys()),
            )
        elif mounts:
            mount_info = [(m.get("Source", "?"), m.get("Destination", "?")) for m in mounts]
            logger.info(
                "Sandbox container %s mounts: %s",
                container_id[:12],
                mount_info,
            )
    except Exception as exc:
        logger.debug("Sandbox mount verification skipped: %s", exc)


def _ensure_sandbox_image(image_name: str, dockerfile_name: str) -> None:
    """Build sandbox image if not present locally.

    Uses APP_HOME (or fallback CWD) as the build context so that
    Dockerfile.sandbox (copied into the image at build time) can be found.
    """
    import docker

    client = docker.from_env()

    try:
        client.images.get(image_name)
        logger.debug("Sandbox image %s already exists", image_name)
        return
    except docker.errors.ImageNotFound:
        pass

    build_path = os.environ.get("APP_HOME", ".")
    dockerfile_path = os.path.join(build_path, dockerfile_name)
    logger.info(
        "Building sandbox image %s from %s (context=%s)...",
        image_name,
        dockerfile_path,
        build_path,
    )
    try:
        client.images.build(
            path=build_path,
            dockerfile=dockerfile_name,
            tag=image_name,
            rm=True,
        )
        logger.info("Sandbox image %s built successfully", image_name)
    except Exception as e:
        logger.error("Failed to build sandbox image %s: %s", image_name, e)
        raise


def _cleanup_stale_sandbox_container(persona: str) -> None:
    """Remove any existing Docker container with the sandbox name for this persona.

    Uses Python Docker SDK (via docker.from_env()) so it respects DOCKER_HOST,
    unlike subprocess("docker rm -f") which requires docker CLI installed.
    """
    container_name = f"sandbox-{persona}"
    try:
        import docker

        client = docker.from_env()
        try:
            container = client.containers.get(container_name)
            container.remove(force=True)
            logger.info("Removed stale sandbox container: %s", container_name)
        except docker.errors.NotFound:
            pass
    except Exception as exc:
        logger.debug("Container cleanup skipped: %s", exc)


def _cleanup_temp_py_files(sandbox_dir: Path) -> int:
    """Remove UUID-named .py temp files created by llm_sandbox on the HOST side.

    Runs directly on the host filesystem (not inside the container) to avoid
    the self-referential problem where cleanup code via session.run() creates
    its own temp file.

    Returns count of removed files.
    """
    pattern = re.compile(r"^[a-f0-9]{32}\.py$", re.I)
    removed = 0
    if sandbox_dir.is_dir():
        for entry in os.listdir(str(sandbox_dir)):
            if pattern.match(entry):
                try:
                    os.remove(os.path.join(str(sandbox_dir), entry))
                    removed += 1
                except OSError:
                    pass
    if removed:
        logger.info("Cleaned up %d temp .py files from %s", removed, sandbox_dir)
    return removed


def _build_container_configs(persona: str) -> tuple[dict, Path | None]:
    """Build container_configs dict and return (configs, sandbox_internal_path).

    sandbox_internal_path is the path usable from the current process to create dirs.
    The volume mount key is resolved in this order:
      1. Explicit MEMORY_MCP_SANDBOX__HOST_DATA_ROOT env var
      2. Auto-detected from own container's Docker mounts (sibling-container mode)
      3. Fallback: same as internal path (local/dev mode)
    """
    from memory_mcp.config.settings import get_settings

    settings = get_settings()

    # Create sandbox dir using container-internal (or local) path
    sandbox_internal = Path(settings.data_root) / "memory" / persona / "sandbox"
    sandbox_internal.mkdir(parents=True, exist_ok=True)
    # Ensure Docker container can write to bind mount (WSL2 permission fix)
    with contextlib.suppress(PermissionError):
        os.chmod(str(sandbox_internal.resolve()), 0o777)  # nosec B103: WSL2 bind mount permission fix

    # Resolve host-side data root (needed when memory-mcp runs in a sibling container)
    host_root = settings.sandbox.host_data_root or _auto_detect_host_data_root(str(settings.data_root))
    sandbox_mount = Path(host_root) / "memory" / persona / "sandbox" if host_root else sandbox_internal.resolve()

    if not host_root:
        logger.warning(
            "Sandbox files will NOT persist on host. Set MEMORY_MCP_SANDBOX__HOST_DATA_ROOT "
            "to the host-side path (e.g. /volume1/docker/MemoryMCP/data). "
            "Internal fallback path: %s",
            sandbox_internal,
        )

    container_configs = {
        "name": f"sandbox-{persona}",  # predictable name for cleanup
        "user": "1000:1000",  # match host user for WSL2 bind mount permissions
        "volumes": {
            str(sandbox_mount): {"bind": WORKSPACE, "mode": "rw"},
        },
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
    }
    logger.info(
        "Sandbox container_configs: persona=%s sandbox_internal=%s sandbox_mount=%s host_root=%s",
        persona,
        sandbox_internal,
        sandbox_mount,
        host_root or "(not set)",
    )
    return container_configs, sandbox_internal


class SandboxSession:
    """Manages sandbox sessions per persona.

    Python: uses ArtifactSandboxSession (stateful IPython + matplotlib artifact extraction).
    Other languages: uses stateless SandboxSession (new container per run).
    """

    def __init__(self, persona: str, docker_host: str = "") -> None:
        self.persona = persona
        self._docker_host = docker_host
        self._python_session = None  # ArtifactSandboxSession or InteractiveSandboxSession
        self._lock = asyncio.Lock()

    def _setup_docker_env(self) -> None:
        """Set DOCKER_HOST env var based on configuration."""
        from memory_mcp.config.settings import get_settings

        settings = get_settings()
        effective_docker_host = _resolve_docker_host(
            self._docker_host or settings.sandbox.docker_host,
            settings.sandbox.docker_sock,
        )
        logger.debug("Sandbox using DOCKER_HOST=%s", effective_docker_host or "(default env)")

        if effective_docker_host:
            os.environ["DOCKER_HOST"] = effective_docker_host
        elif "DOCKER_HOST" in os.environ:
            del os.environ["DOCKER_HOST"]

    async def _ensure_python_started(self) -> None:
        if self._python_session is not None:
            return
        try:
            self._setup_docker_env()
            container_configs, _ = _build_container_configs(self.persona)
            from memory_mcp.config.settings import get_settings

            sandbox_image = get_settings().sandbox.image

            # Remove any stale container with the same name
            _cleanup_stale_sandbox_container(self.persona)

            # Ensure sandbox image exists (build if not present locally)
            _ensure_sandbox_image(sandbox_image, "Dockerfile.sandbox")

            # Try ArtifactSandboxSession first (matplotlib/plot support)
            def _start_session():
                try:
                    from llm_sandbox import ArtifactSandboxSession

                    session = ArtifactSandboxSession(
                        lang="python",
                        image=sandbox_image,
                        runtime_configs=container_configs,
                    )
                except (ImportError, AttributeError):
                    from llm_sandbox import InteractiveSandboxSession

                    session = InteractiveSandboxSession(
                        lang="python",
                        kernel_type="ipython",
                        image=sandbox_image,
                        runtime_configs=container_configs,
                    )
                session.__enter__()
                return session

            self._python_session = await asyncio.to_thread(_start_session)

            # Initialize workspace directories
            await asyncio.to_thread(
                self._python_session.run,
                f"import os; os.makedirs('{UPLOADS_DIR}', exist_ok=True); os.makedirs('{OUTPUT_DIR}', exist_ok=True)",
            )
            # Drain any startup messages from ArtifactSandboxSession
            with contextlib.suppress(Exception):
                await asyncio.to_thread(self._python_session.run, "pass")

            # Verify volume mount was applied
            _verify_sandbox_mounts(self._python_session, container_configs, self.persona)

            logger.info("Python sandbox session started for persona=%s", self.persona)
        except Exception as e:
            self._python_session = None
            error_msg = str(e)
            if "FileNotFoundError" in error_msg or "Connection aborted" in error_msg:
                if platform.system() == "Windows":
                    hint = "Docker Desktop が起動していることを確認してください。"
                else:
                    candidates = _SOCKET_CANDIDATES.get(platform.system(), ["/var/run/docker.sock"])
                    checked = ", ".join(candidates)
                    hint = (
                        f"Docker ソケットが見つかりません（確認済み: {checked}）。"
                        " docker-compose.yml の volumes に /var/run/docker.sock:/var/run/docker.sock が設定されているか確認してください。"
                    )
                raise RuntimeError(f"Docker に接続できませんでした: {hint}") from e
            raise RuntimeError(f"Failed to start sandbox: {e}") from e

    async def execute(self, code: str, language: str = "python", libraries: list[str] | None = None) -> ExecResult:
        """Execute code in the appropriate sandbox session.

        bash/shell/shell は専用コンテナが無いため、Python IPython セッション内で
        subprocess 経由で実行する。
        """
        if language in ("python", "py", "bash", "shell", "sh"):
            if language in ("bash", "shell", "sh"):
                import json as _json

                # Strip IPython magic ! prefix — users may copy commands from
                # Python sandbox (!ls) but use language="bash" where ! is invalid
                shell_code = code.lstrip()
                if shell_code.startswith("!"):
                    shell_code = shell_code[1:].lstrip()
                code = (
                    "import subprocess as _sp; "
                    f"r = _sp.run({_json.dumps(shell_code)}, "
                    "shell=True, capture_output=True, text=True); "
                    "print(r.stdout, end=''); "
                    "__import__('sys').stderr.write(r.stderr)"
                )
            return await self._execute_python(code)
        return await self._execute_stateless(code, language, libraries or [])

    async def _execute_python(self, code: str) -> ExecResult:
        async with self._lock:
            await self._ensure_python_started()
            try:
                result = await asyncio.to_thread(self._python_session.run, code)
                stdout = (
                    (getattr(result, "stdout", "") or "")
                    .replace("Python plot detection setup complete\n", "")
                    .replace("Python plot detection setup complete", "")
                )
                stderr = getattr(result, "stderr", "") or ""
                exit_code = getattr(result, "exit_code", 0) or 0

                # Extract matplotlib/plot artifacts if available
                artifacts: list[str] = []
                plots = getattr(result, "plots", None)
                if plots:
                    for plot in plots:
                        b64 = getattr(plot, "content_base64", None) or getattr(plot, "data", None)
                        if b64:
                            artifacts.append(b64)

                # Clean up temp .py files created by llm_sandbox on the HOST side
                # (each run() writes code to a UUID-named temp file before execution)
                # Running cleanup directly on host avoids creating MORE temp files
                try:
                    from memory_mcp.config.settings import get_settings

                    sandbox_dir = Path(get_settings().data_root) / "memory" / self.persona / "sandbox"
                    await asyncio.to_thread(_cleanup_temp_py_files, sandbox_dir)
                except Exception:
                    pass

                return ExecResult(
                    stdout=stdout, stderr=stderr, exit_code=exit_code, artifacts=artifacts, language="python"
                )
            except Exception as e:
                logger.warning("Sandbox Python execute error: %s", e)
                return ExecResult(stdout="", stderr=str(e), exit_code=1, language="python")

    async def _execute_stateless(self, code: str, language: str, libraries: list[str]) -> ExecResult:
        """Execute code in a stateless container (new container per run)."""
        self._setup_docker_env()

        def _run() -> ExecResult:
            try:
                from llm_sandbox import SandboxSession as LlmStatelessSession

                container_configs, _ = _build_container_configs(self.persona)
                # Remove volume for stateless sessions if needed (faster startup)
                # Keep security hardening
                with LlmStatelessSession(
                    lang=language,
                    runtime_configs={
                        "cap_drop": container_configs.get("cap_drop", ["ALL"]),
                        "security_opt": container_configs.get("security_opt", ["no-new-privileges:true"]),
                    },
                ) as session:
                    if libraries:
                        session.install(libraries)
                    result = session.run(code)
                    # Clean up temp .py files on the host side
                    from memory_mcp.config.settings import get_settings

                    with contextlib.suppress(Exception):
                        _cleanup_temp_py_files(Path(get_settings().data_root) / "memory" / self.persona / "sandbox")
                    return ExecResult(
                        stdout=getattr(result, "stdout", "") or "",
                        stderr=getattr(result, "stderr", "") or "",
                        exit_code=getattr(result, "exit_code", 0) or 0,
                        language=language,
                    )
            except Exception as e:
                return ExecResult(stdout="", stderr=str(e), exit_code=1, language=language)

        return await asyncio.to_thread(_run)

    async def install_packages(self, packages: list[str]) -> str:
        """Install Python packages in the persistent Python session."""
        async with self._lock:
            await self._ensure_python_started()
            try:
                await asyncio.to_thread(self._python_session.install, packages)
                return f"インストール完了: {', '.join(packages)}"
            except Exception as e:
                logger.warning("Sandbox install error: %s", e)
                return f"インストール失敗: {e}"

    async def reset(self) -> None:
        """Close and reset the Python session (will be re-created on next execute)."""
        async with self._lock:
            if self._python_session is not None:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(self._python_session.__exit__, None, None, None)
                self._python_session = None
                logger.info("Python sandbox session reset for persona=%s", self.persona)

    async def upload_file(self, local_path: str, filename: str) -> str:
        """Upload a file to /sandbox/uploads/ in the sandbox."""
        async with self._lock:
            await self._ensure_python_started()
            remote_path = f"{UPLOADS_DIR}/{filename}"
            await asyncio.to_thread(self._python_session.copy_to_runtime, local_path, remote_path)
            return remote_path

    async def list_files(self, path: str = WORKSPACE) -> list[SandboxFileInfo]:
        """List files in sandbox path."""
        async with self._lock:
            await self._ensure_python_started()

            # --- DEBUG: verify sandbox state ---
            try:
                check = await asyncio.to_thread(
                    self._python_session.run,
                    f"import os; print('EXISTS:' + str(os.path.exists({path!r}))); print('ISDIR:' + str(os.path.isdir({path!r}))); print('LISTDIR:' + str(os.listdir({path!r})))",
                )
                logger.info("list_files pre-check path=%s: %s", path, (check.stdout or "").strip().replace("\n", " | "))
            except Exception as e:
                logger.warning("list_files pre-check failed: %s", e)
            # --- END DEBUG ---

            code = f"""
import os, json, sys
target = {path!r}
result = []
sys.stderr.write(f"[DEBUG] target={{target}} exists={{os.path.exists(target)}}\\n")
if not os.path.exists(target):
    result = [{{"error": f"Path does not exist: {{target}}"}}]
else:
    try:
        entries = list(os.scandir(target))
        sys.stderr.write(f"[DEBUG] scandir found {{len(entries)}} entries\\n")
        for entry in entries:
            try:
                st = entry.stat(follow_symlinks=False)
                is_dir = (st.st_mode & 0o170000) == 0o040000  # S_ISDIR
                size = st.st_size if not is_dir else 0
            except OSError:
                is_dir, size = False, 0
            result.append({{"name": entry.name, "path": entry.path, "is_dir": is_dir, "size": size}})
    except Exception as e:
        sys.stderr.write(f"[DEBUG] scandir error: {{e}}\\n")
        result = [{{"error": str(e), "target": target}}]
sys.stderr.write(f"[DEBUG] result count={{len(result)}}\\n")
print(json.dumps(result))
"""
            try:
                exec_result = await asyncio.to_thread(self._python_session.run, code)
                import json

                raw_stdout = (
                    (exec_result.stdout or "")
                    .replace("Python plot detection setup complete\n", "")
                    .replace("Python plot detection setup complete", "")
                    .strip()
                )
                raw_stderr = (exec_result.stderr or "").strip()
                logger.info(
                    "list_files path=%s stdout_len=%d stderr_len=%d stdout_preview=%s stderr_preview=%s",
                    path,
                    len(raw_stdout),
                    len(raw_stderr),
                    raw_stdout[:200] if raw_stdout else "(empty)",
                    raw_stderr[:200] if raw_stderr else "(empty)",
                )
                entries = json.loads(raw_stdout)
                file_infos = [SandboxFileInfo(**e) for e in entries if "error" not in e]
                if not file_infos and entries:
                    errors = [e for e in entries if "error" in e]
                    logger.warning("list_files path=%s errors: %s", path, errors)
                logger.info("list_files path=%s found %d entries", path, len(file_infos))
                return file_infos
            except Exception as e:
                logger.warning("list_files error for path=%s: %s", path, e)
                # Fallback: try os.listdir
                try:
                    fallback_code = f"""
import os, json
target = {path!r}
result = []
for name in os.listdir(target):
    fp = os.path.join(target, name)
    try:
        is_dir = os.path.isdir(fp)
        size = os.path.getsize(fp) if not is_dir else 0
    except OSError:
        is_dir, size = False, 0
    result.append({{"name": name, "path": fp, "is_dir": is_dir, "size": size}})
print(json.dumps(result))
"""
                    fb_result = await asyncio.to_thread(self._python_session.run, fallback_code)
                    fb_stdout = (
                        (fb_result.stdout or "")
                        .replace("Python plot detection setup complete\n", "")
                        .replace("Python plot detection setup complete", "")
                        .strip()
                    )
                    fb_entries = json.loads(fb_stdout)
                    fb_infos = [SandboxFileInfo(**e) for e in fb_entries if "error" not in e]
                    logger.info("list_files fallback path=%s found %d entries", path, len(fb_infos))
                    return fb_infos
                except Exception as fb_e:
                    logger.warning("list_files fallback also failed: %s", fb_e)
                    return []

    async def read_file(self, remote_path: str) -> bytes:
        """Download a file from the sandbox."""
        async with self._lock:
            await self._ensure_python_started()
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tmp_path = tf.name
            try:
                await asyncio.to_thread(self._python_session.copy_from_runtime, remote_path, tmp_path)
                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                with contextlib.suppress(Exception):
                    os.unlink(tmp_path)

    async def delete_file(self, remote_path: str) -> bool:
        """Delete a file in the sandbox."""
        async with self._lock:
            await self._ensure_python_started()
            try:
                result = await asyncio.to_thread(
                    self._python_session.run,
                    f"import os; os.remove({remote_path!r}); print('deleted')",
                )
                return "deleted" in (result.stdout or "")
            except Exception:
                return False

    async def read_file_text(self, remote_path: str) -> str:
        """Read a file from the sandbox as text."""
        async with self._lock:
            await self._ensure_python_started()
            code = f"""
try:
    with open({remote_path!r}, 'r', encoding='utf-8') as f:
        print(f.read(), end='')
except Exception as e:
    print(f'__ERROR__: {{e}}', end='')
"""
            result = await asyncio.to_thread(self._python_session.run, code)
            text = getattr(result, "stdout", "") or ""
            if text.startswith("__ERROR__:"):
                raise RuntimeError(text[len("__ERROR__:") :].strip())
            return text

    async def read_image(self, remote_path: str, max_dim: int = 1568) -> dict:
        """Read and preprocess an image from the sandbox.

        Returns a dict with:
            content_base64, content_type, size, path
            If resized: resized=True, orig_size, orig_dims, new_dims, new_size
        """
        import base64 as _b64
        import json as _json

        preprocess_code = (
            "import os, json\n"
            f"p = {_json.dumps(remote_path)}\n"
            "r = {'ok': False}\n"
            "if not os.path.exists(p):\n"
            " r['error'] = f'File not found: {p}'\n"
            "else:\n"
            " sz = os.path.getsize(p)\n"
            " try:\n"
            "  from PIL import Image\n"
            f"  im = Image.open(p); w, h = im.size\n"
            f"  if w > {max_dim} or h > {max_dim} or sz > 500*1024:\n"
            f"   im.thumbnail(({max_dim}, {max_dim}), Image.LANCZOS)\n"
            "   tmp = '/sandbox/_rszd_' + os.path.basename(p) + '.jpg'\n"
            "   im.convert('RGB').save(tmp, 'JPEG', quality=80, optimize=True)\n"
            "   r = {'ok': True, 'path': tmp, 'orig_size': sz, 'new_size': os.path.getsize(tmp), "
            f"  'orig_w': w, 'orig_h': h, 'new_w': im.size[0], 'new_h': im.size[1]}}\n"
            "  else:\n"
            "   r = {'ok': True, 'path': p, 'size': sz}\n"
            " except ImportError:\n"
            "  r = {'ok': True, 'path': p, 'size': sz, 'nopil': True}\n"
            " except Exception as e:\n"
            "  r['error'] = str(e)\n"
            "print(json.dumps(r))"
        )
        async with self._lock:
            await self._ensure_python_started()
            result = await asyncio.to_thread(self._python_session.run, preprocess_code)
            pre_raw = (result.stdout or "").strip()
            if not pre_raw:
                raise RuntimeError("Image preprocessing failed: empty stdout")
            try:
                pre = _json.loads(pre_raw)
            except Exception as e:
                raise RuntimeError(f"Image preprocessing JSON parse failed: {pre_raw[:200]}") from e

            if pre.get("error"):
                raise RuntimeError(pre["error"])

            # If PIL not available, try installing it (one-time per session)
            if pre.get("nopil"):
                try:
                    await self.install_packages(["Pillow"])
                    retry_result = await asyncio.to_thread(self._python_session.run, preprocess_code)
                    pre = _json.loads((retry_result.stdout or "").strip())
                except Exception:
                    pass  # Fall through — use unresized image

            read_path = pre.get("path", remote_path)
            raw = await self.read_file(read_path)

            # Detect image type from magic bytes
            content_type = "image/jpeg" if read_path.endswith(".jpg") else None
            if not content_type:
                if len(raw) >= 4:
                    if raw[:4] == b"\x89PNG":
                        content_type = "image/png"
                    elif raw[:2] == b"\xff\xd8":
                        content_type = "image/jpeg"
                    elif raw[:3] == b"GIF":
                        content_type = "image/gif"
                    elif len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
                        content_type = "image/webp"
                if not content_type:
                    content_type = "image/png"  # fallback

            b64_str = _b64.b64encode(raw).decode("ascii")
            out: dict = {
                "content_base64": b64_str,
                "content_type": content_type,
                "size": len(raw),
                "path": remote_path,
            }
            if pre.get("orig_size"):
                out["resized"] = True
                out["orig_size"] = pre["orig_size"]
                out["orig_dims"] = f"{pre['orig_w']}x{pre['orig_h']}"
                out["new_dims"] = f"{pre['new_w']}x{pre['new_h']}"
                out["new_size"] = pre["new_size"]

            # Clean up temp resized file
            if read_path != remote_path:
                await self.delete_file(read_path)

            return out

    async def write_file_text(self, remote_path: str, content: str) -> None:
        """Write text content to a file in the sandbox."""
        async with self._lock:
            await self._ensure_python_started()
            import json as _json

            safe_content = _json.dumps(content)
            code = f"""
import os
os.makedirs(os.path.dirname({remote_path!r}) or '.', exist_ok=True)
with open({remote_path!r}, 'w', encoding='utf-8') as f:
    f.write({safe_content})
print('ok')
"""
            await asyncio.to_thread(self._python_session.run, code)

    async def get_file_tree(self, root: str = WORKSPACE) -> list[dict]:
        """Return a recursive file tree rooted at root."""
        async with self._lock:
            await self._ensure_python_started()
            code = f"""
import os, json
def _tree(path, max_depth=4, depth=0):
    result = []
    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        for e in entries:
            node = {{"name": e.name, "path": e.path, "is_dir": e.is_dir(), "size": 0 if e.is_dir() else e.stat().st_size}}
            if e.is_dir() and depth < max_depth:
                node["children"] = _tree(e.path, max_depth, depth + 1)
            result.append(node)
    except PermissionError:
        pass
    return result
print(json.dumps(_tree({root!r})))
"""
            try:
                result = await asyncio.to_thread(self._python_session.run, code)
                import json

                raw = (
                    (result.stdout or "")
                    .replace("Python plot detection setup complete\n", "")
                    .replace("Python plot detection setup complete", "")
                    .strip()
                )
                return json.loads(raw) or []
            except Exception as e:
                logger.warning("get_file_tree error: %s", e)
                return []

    def close(self) -> None:
        if self._python_session is not None:
            # Clean up temp .py files on the host side
            try:
                from memory_mcp.config.settings import get_settings

                _cleanup_temp_py_files(Path(get_settings().data_root) / "memory" / self.persona / "sandbox")
            except Exception:
                pass  # cleanup is best-effort
            with contextlib.suppress(Exception):
                self._python_session.__exit__(None, None, None)
            self._python_session = None


# Global session registry (persona → SandboxSession)
_sessions: dict[str, SandboxSession] = {}


def get_sandbox_session(persona: str, docker_host: str = "") -> SandboxSession:
    """Get or create a sandbox session for persona.

    If docker_host is provided it overrides the global SandboxConfig.docker_host.
    When the docker_host changes for an existing session the old session is closed
    and a new one is created so the new host takes effect immediately.
    """
    existing = _sessions.get(persona)
    if existing is not None and existing._docker_host == docker_host:
        return existing
    if existing is not None:
        existing.close()
    session = SandboxSession(persona, docker_host=docker_host)
    _sessions[persona] = session
    return session


def close_sandbox_session(persona: str) -> None:
    """Close and remove sandbox session for persona."""
    if persona in _sessions:
        _sessions[persona].close()
        del _sessions[persona]
