from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
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


def _build_container_configs(persona: str) -> tuple[dict, Path | None]:
    """Build container_configs dict and return (configs, workspace_internal_path).

    workspace_internal_path is the path usable from the current process to create dirs.
    The volume mount key uses host_data_root if available (sibling container support).
    Returns (configs, None) if workspace volume mount is skipped.
    """
    from memory_mcp.config.settings import get_settings

    settings = get_settings()

    # Create workspace dir using container-internal (or local) path
    workspace_internal = Path(settings.data_root) / "sandbox" / persona / "workspace"
    workspace_internal.mkdir(parents=True, exist_ok=True)

    # For sibling-container deployments, use host_data_root for the volume mount key
    if settings.sandbox.host_data_root:
        workspace_mount = Path(settings.sandbox.host_data_root) / "sandbox" / persona / "workspace"
    else:
        workspace_mount = workspace_internal

    container_configs = {
        "volumes": {
            str(workspace_mount): {"bind": WORKSPACE, "mode": "rw"},
        },
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
    }
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
                f"import os; os.makedirs('{UPLOADS_DIR}', exist_ok=True); "
                f"os.makedirs('{OUTPUT_DIR}', exist_ok=True); print('workspace ready')",
            )
            logger.info("Python sandbox session started for persona=%s", self.persona)
        except Exception as e:
            self._python_session = None
            error_msg = str(e)
            if "FileNotFoundError" in error_msg or "Connection aborted" in error_msg:
                if platform.system() == "Windows":
                    hint = (
                        "Docker Desktop が起動していることを確認してください。"
                    )
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
                stdout = getattr(result, "stdout", "") or ""
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

                return ExecResult(stdout=stdout, stderr=stderr, exit_code=exit_code, artifacts=artifacts, language="python")
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
                try:
                    await asyncio.to_thread(self._python_session.__exit__, None, None, None)
                except Exception:
                    pass
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

    def close(self) -> None:
        if self._python_session is not None:
            try:
                self._python_session.__exit__(None, None, None)
            except Exception:
                pass
            self._python_session = None


# Global session registry (persona → SandboxSession)
_sessions: dict[str, SandboxSession] = {}


def get_sandbox_session(persona: str, docker_host: str = "") -> SandboxSession:
    """Get or create a sandbox session for persona."""
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


def _resolve_docker_host(explicit_host: str, docker_sock_override: str) -> str:
    """Return the DOCKER_HOST value to use, or empty string to keep current env."""
    # Explicit TCP/npipe host always wins
    if explicit_host:
        return explicit_host

    # Windows: use named pipe
    if platform.system() == "Windows":
        return "npipe:////./pipe/docker_engine"

    # Unix: scan candidate socket paths
    candidates: list[str] = []
    if docker_sock_override:
        candidates.append(docker_sock_override)
    candidates.extend(_SOCKET_CANDIDATES.get(platform.system(), ["/var/run/docker.sock"]))

    for path in candidates:
        if os.path.exists(path):
            return f"unix://{path}"

    # Nothing found – return empty so we let docker.from_env() try (and fail with its own error)
    return ""


@dataclass
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


@dataclass
class SandboxFileInfo:
    name: str
    path: str
    is_dir: bool
    size: int = 0


class SandboxSession:
    """Wraps an InteractiveSandboxSession with lifecycle management."""

    def __init__(self, persona: str, docker_host: str = "") -> None:
        self.persona = persona
        self._docker_host = docker_host
        self._session = None
        self._lock = asyncio.Lock()

    async def _ensure_started(self) -> None:
        if self._session is not None:
            return
        try:
            from llm_sandbox import InteractiveSandboxSession

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

            # Resolve persistent workspace path on the host
            workspace_host = Path(settings.data_root) / "sandbox" / self.persona / "workspace"
            workspace_host.mkdir(parents=True, exist_ok=True)

            container_configs = {
                "volumes": {
                    str(workspace_host): {"bind": WORKSPACE, "mode": "rw"},
                },
                # Security hardening: prevent container escape
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
            }

            self._session = InteractiveSandboxSession(
                lang="python",
                kernel_type="ipython",
                container_configs=container_configs,
            )
            # __enter__ starts the container and waits for the IPython kernel —
            # run in a thread to avoid blocking the async event loop (can take 30s+)
            await asyncio.to_thread(self._session.__enter__)
            # Create workspace sub-directories — also blocking
            await asyncio.to_thread(
                self._session.run,
                f"import os; os.makedirs('{UPLOADS_DIR}', exist_ok=True); "
                f"os.makedirs('{OUTPUT_DIR}', exist_ok=True); print('workspace ready')",
            )
            logger.info("Sandbox session started for persona=%s", self.persona)
        except Exception as e:
            self._session = None
            error_msg = str(e)
            if "FileNotFoundError" in error_msg or "Connection aborted" in error_msg:
                candidates = _SOCKET_CANDIDATES.get(platform.system(), ["/var/run/docker.sock"])
                if platform.system() == "Windows":
                    hint = (
                        "Docker Desktop が起動していることを確認してください。"
                        " npipe:////./pipe/docker_engine または tcp://localhost:2375 を設定の「Docker Host」欄に入力できます。"
                    )
                else:
                    checked = ", ".join(candidates)
                    hint = (
                        f"Docker ソケットが見つかりません（確認済み: {checked}）。"
                        " docker-compose を使っている場合は sandbox-docker サービスが起動しているか確認してください"
                        " (`docker-compose ps sandbox-docker`)。"
                        " MEMORY_MCP_SANDBOX__DOCKER_HOST=tcp://sandbox-docker:2375 を設定してください。"
                        " ローカルで Python を直接起動している場合は Docker Desktop が起動しているか確認してください。"
                    )
                raise RuntimeError(f"Docker に接続できませんでした: {hint}") from e
            raise RuntimeError(f"Failed to start sandbox: {e}") from e

    async def execute(self, code: str, language: str = "python") -> ExecResult:
        async with self._lock:
            await self._ensure_started()
            try:
                if language in ("bash", "sh"):
                    code = (
                        f"import subprocess; r = subprocess.run({code!r}, shell=True, "
                        f"capture_output=True, text=True); print(r.stdout); print(r.stderr, end='')"
                    )
                result = await asyncio.to_thread(self._session.run, code)
                return ExecResult(
                    stdout=getattr(result, "stdout", "") or "",
                    stderr=getattr(result, "stderr", "") or "",
                    exit_code=getattr(result, "exit_code", 0) or 0,
                )
            except Exception as e:
                logger.warning("Sandbox execute error: %s", e)
                return ExecResult(stdout="", stderr=str(e), exit_code=1)

    async def upload_file(self, local_path: str, filename: str) -> str:
        """Upload a file to /workspace/uploads/ in the sandbox."""
        async with self._lock:
            await self._ensure_started()
            remote_path = f"{UPLOADS_DIR}/{filename}"
            await asyncio.to_thread(self._session.copy_to_runtime, local_path, remote_path)
            return remote_path

    async def list_files(self, path: str = WORKSPACE) -> list[SandboxFileInfo]:
        """List files in sandbox path."""
        async with self._lock:
            await self._ensure_started()
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
                exec_result = await asyncio.to_thread(self._session.run, code)
                import json

                entries = json.loads(exec_result.stdout.strip())
                return [SandboxFileInfo(**e) for e in entries if "error" not in e]
            except Exception as e:
                logger.warning("list_files error: %s", e)
                return []

    async def read_file(self, remote_path: str) -> bytes:
        """Download a file from the sandbox."""
        async with self._lock:
            await self._ensure_started()
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tmp_path = tf.name
            try:
                await asyncio.to_thread(self._session.copy_from_runtime, remote_path, tmp_path)
                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                with contextlib.suppress(Exception):
                    os.unlink(tmp_path)

    async def delete_file(self, remote_path: str) -> bool:
        """Delete a file in the sandbox."""
        async with self._lock:
            await self._ensure_started()
            try:
                result = await asyncio.to_thread(
                    self._session.run,
                    f"import os; os.remove({remote_path!r}); print('deleted')",
                )
                return "deleted" in (result.stdout or "")
            except Exception:
                return False

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.__exit__(None, None, None)
            except Exception:
                pass
            self._session = None


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
