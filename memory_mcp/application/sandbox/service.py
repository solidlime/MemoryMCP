from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = "/workspace"
UPLOADS_DIR = f"{WORKSPACE}/uploads"
OUTPUT_DIR = f"{WORKSPACE}/output"


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
            effective_docker_host = self._docker_host or settings.sandbox.docker_host

            if not effective_docker_host:
                # Auto-detect Windows Docker Desktop named pipe
                import platform

                if platform.system() == "Windows":
                    effective_docker_host = "npipe:////./pipe/docker_engine"

            # Set DOCKER_HOST so the Docker Python SDK connects to the right daemon
            if effective_docker_host:
                os.environ["DOCKER_HOST"] = effective_docker_host
            elif "DOCKER_HOST" in os.environ:
                # Clear any leftover env var so we fall back to the local socket
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
            self._session.__enter__()
            # Create sub-directories inside the mounted workspace
            self._session.run(
                f"import os; os.makedirs('{UPLOADS_DIR}', exist_ok=True); "
                f"os.makedirs('{OUTPUT_DIR}', exist_ok=True); print('workspace ready')"
            )
            logger.info("Sandbox session started for persona=%s", self.persona)
        except Exception as e:
            self._session = None
            error_msg = str(e)
            if "FileNotFoundError" in error_msg or "Connection aborted" in error_msg:
                import platform

                if platform.system() == "Windows":
                    hint = (
                        "Docker Desktop が起動していることを確認し、"
                        "設定の「Docker Host」欄に npipe:////./pipe/docker_engine を入力してください。"
                        " TCP を有効にした場合は tcp://localhost:2375 でも接続できます。"
                    )
                else:
                    hint = (
                        "Docker デーモンが起動していることを確認してください。"
                        " DinD 環境では docker-compose.yml で /var/run/docker.sock をマウントしてください。"
                    )
                raise RuntimeError(f"Docker に接続できませんでした: {hint} (原因: {e})") from e
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
