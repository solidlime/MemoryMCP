from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
from dataclasses import dataclass

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

    def __init__(self, persona: str) -> None:
        self.persona = persona
        self._session = None
        self._lock = asyncio.Lock()

    async def _ensure_started(self) -> None:
        if self._session is not None:
            return
        try:
            from llm_sandbox import InteractiveSandboxSession

            self._session = InteractiveSandboxSession(lang="python", kernel_type="ipython")
            self._session.__enter__()
            self._session.run(
                f"import os; os.makedirs('{UPLOADS_DIR}', exist_ok=True); "
                f"os.makedirs('{OUTPUT_DIR}', exist_ok=True); print('workspace ready')"
            )
            logger.info("Sandbox session started for persona=%s", self.persona)
        except Exception as e:
            self._session = None
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


def get_sandbox_session(persona: str) -> SandboxSession:
    """Get or create a sandbox session for persona."""
    if persona not in _sessions:
        _sessions[persona] = SandboxSession(persona)
    return _sessions[persona]


def close_sandbox_session(persona: str) -> None:
    """Close and remove sandbox session for persona."""
    if persona in _sessions:
        _sessions[persona].close()
        del _sessions[persona]
