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

WORKSPACE = "/workspace"
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

# llm-sandbox language → image tag name mapping
_LANG_IMAGE_TAGS: dict[str, str] = {
    "python": "python-311-bullseye",
    "javascript": "node-22-bullseye",
    "java": "java-21-bullseye",
    "cpp": "cpp-bullseye",
    "go": "go-1.21-bullseye",
    "r": "r-4.3-bullseye",
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
            capture_output=True, text=True, timeout=10,
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
                "Files written to /workspace will NOT persist on host. "
                "llm_sandbox may not be applying container_configs['volumes'].",
                container_id[:12], list(expected_volumes.keys()),
            )
        elif mounts:
            mount_info = [(m.get("Source", "?"), m.get("Destination", "?")) for m in mounts]
            logger.info(
                "Sandbox container %s mounts: %s", container_id[:12], mount_info,
            )
    except Exception as exc:
        logger.debug("Sandbox mount verification skipped: %s", exc)


def _build_container_configs(persona: str) -> tuple[dict, Path | None]:
    """Build container_configs dict and return (configs, workspace_internal_path).

    workspace_internal_path is the path usable from the current process to create dirs.
    The volume mount key is resolved in this order:
      1. Explicit MEMORY_MCP_SANDBOX__HOST_DATA_ROOT env var
      2. Auto-detected from own container's Docker mounts (sibling-container mode)
      3. Fallback: same as internal path (local/dev mode)
    """
    from memory_mcp.config.settings import get_settings

    settings = get_settings()

    # Create workspace dir using container-internal (or local) path
    workspace_internal = Path(settings.data_root) / "memory" / persona / "workspace"
    workspace_internal.mkdir(parents=True, exist_ok=True)

    # Resolve host-side data root (needed when memory-mcp runs in a sibling container)
    host_root = settings.sandbox.host_data_root or _auto_detect_host_data_root(str(settings.data_root))
    workspace_mount = Path(host_root) / "memory" / persona / "workspace" if host_root else workspace_internal

    if not host_root:
        logger.warning(
            "Sandbox files will NOT persist on host. Set MEMORY_MCP_SANDBOX__HOST_DATA_ROOT "
            "to the host-side path (e.g. /volume1/docker/MemoryMCP/data). "
            "Internal fallback path: %s",
            workspace_internal,
        )

    container_configs = {
        "volumes": {
            str(workspace_mount): {"bind": WORKSPACE, "mode": "rw"},
        },
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
    }
    logger.info(
        "Sandbox container_configs: persona=%s workspace_internal=%s workspace_mount=%s host_root=%s",
        persona, workspace_internal, workspace_mount, host_root or "(not set)"
    )
    return container_configs, workspace_internal


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

            # Try ArtifactSandboxSession first (matplotlib/plot support)
            def _start_session():
                try:
                    from llm_sandbox import ArtifactSandboxSession

                    session = ArtifactSandboxSession(
                        lang="python",
                        container_configs=container_configs,
                    )
                except (ImportError, AttributeError):
                    from llm_sandbox import InteractiveSandboxSession

                    session = InteractiveSandboxSession(
                        lang="python",
                        kernel_type="ipython",
                        container_configs=container_configs,
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
        """Execute code in the appropriate sandbox session."""
        if language in ("python", "py"):
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
                    container_configs={
                        "cap_drop": container_configs.get("cap_drop", ["ALL"]),
                        "security_opt": container_configs.get("security_opt", ["no-new-privileges:true"]),
                    },
                ) as session:
                    if libraries:
                        session.install(libraries)
                    result = session.run(code)
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
        """Upload a file to /workspace/uploads/ in the sandbox."""
        async with self._lock:
            await self._ensure_python_started()
            remote_path = f"{UPLOADS_DIR}/{filename}"
            await asyncio.to_thread(self._python_session.copy_to_runtime, local_path, remote_path)
            return remote_path

    async def list_files(self, path: str = WORKSPACE) -> list[SandboxFileInfo]:
        """List files in sandbox path."""
        async with self._lock:
            await self._ensure_python_started()
            code = f"""
import os, json
result = []
try:
    for entry in os.scandir({path!r}):
        result.append({{"name": entry.name, "path": entry.path, "is_dir": entry.is_dir(), "size": entry.stat().st_size if not entry.is_dir() else 0}})
except Exception as e:
    result = [{{"error": str(e)}}]
print(json.dumps(result))
"""
            try:
                exec_result = await asyncio.to_thread(self._python_session.run, code)
                import json

                entries = json.loads(exec_result.stdout.strip())
                return [SandboxFileInfo(**e) for e in entries if "error" not in e]
            except Exception as e:
                logger.warning("list_files error: %s", e)
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

                return json.loads((result.stdout or "").strip()) or []
            except Exception as e:
                logger.warning("get_file_tree error: %s", e)
                return []

    def close(self) -> None:
        if self._python_session is not None:
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
