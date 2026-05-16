"""Tests for MCP tool handlers: sandbox and sandbox_files."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_mcp.application.sandbox.service import ExecResult, SandboxFileInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_app_context():
    ctx = MagicMock()
    return ctx


@pytest.fixture
def registered_tools(mock_app_context):
    """Call register_tools with a mock FastMCP, capturing tool functions."""
    tools: dict[str, object] = {}

    def mock_tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mock_mcp = MagicMock()
    mock_mcp.tool = mock_tool_decorator

    with (
        patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_registry_cls,
        patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
    ):
        mock_registry_cls.get.return_value = mock_app_context

        from memory_mcp.api.mcp.tools import register_tools

        register_tools(mock_mcp)
        yield tools, mock_app_context, mock_registry_cls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_settings(enabled: bool = True):
    """Create a settings mock with sandbox.enabled set."""
    s = MagicMock()
    s.sandbox.enabled = enabled
    return s


def _mock_sandbox_session() -> MagicMock:
    """Create an AsyncMock sandbox session."""
    return AsyncMock()


# ============================================================================
# sandbox()
# ============================================================================


class TestSandbox:
    """Tests for the sandbox tool (execute code in Docker sandbox)."""

    @pytest.mark.asyncio
    async def test_execute_python_success(self, registered_tools):
        """Executing valid Python code returns stdout."""
        tools, ctx, _ = registered_tools
        sandbox_tool = tools["sandbox"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.execute.return_value = ExecResult(
                stdout="hello\nworld",
                stderr="",
                exit_code=0,
                artifacts=[],
            )
            mock_get_session.return_value = session

            result = await sandbox_tool(code="print('hello')")

        assert "hello" in result
        assert "world" in result
        session.execute.assert_called_once_with("print('hello')", language="python")

    @pytest.mark.asyncio
    async def test_execute_with_error(self, registered_tools):
        """Code with errors should return stderr."""
        tools, ctx, _ = registered_tools
        sandbox_tool = tools["sandbox"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.execute.return_value = ExecResult(
                stdout="",
                stderr="NameError: name 'x' is not defined",
                exit_code=1,
                artifacts=[],
            )
            mock_get_session.return_value = session

            result = await sandbox_tool(code="print(x)")

        assert "[stderr]" in result
        assert "NameError" in result
        assert "exit code: 1" in result

    @pytest.mark.asyncio
    async def test_execute_missing_code(self, registered_tools):
        """Disabled sandbox should return an error message."""
        tools, ctx, _ = registered_tools
        sandbox_tool = tools["sandbox"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=False)

            result = await sandbox_tool(code="print('hi')")

        assert "not enabled" in result.lower()
        mock_get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_service_failure(self, registered_tools):
        """Service failure (exception) should return a sandbox error."""
        tools, ctx, _ = registered_tools
        sandbox_tool = tools["sandbox"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.execute.side_effect = RuntimeError("Docker not available")
            mock_get_session.return_value = session

            result = await sandbox_tool(code="print('hi')")

        assert "Sandbox error" in result
        assert "Docker not available" in result


# ============================================================================
# sandbox_files()
# ============================================================================


class TestSandboxFiles:
    """Tests for sandbox_files tool (sandbox file CRUD operations)."""

    @pytest.mark.asyncio
    async def test_list_files_success(self, registered_tools):
        """Listing files should return file list."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.list_files.return_value = [
                SandboxFileInfo(name="test.txt", path="/sandbox/test.txt", is_dir=False, size=10),
                SandboxFileInfo(name="subdir", path="/sandbox/subdir", is_dir=True, size=0),
            ]
            mock_get_session.return_value = session

            result = await sf_tool(operation="list")

        data = json.loads(result)
        assert data["ok"] is True
        assert len(data["files"]) == 2
        assert data["files"][0]["name"] == "test.txt"
        assert data["files"][0]["is_dir"] is False
        assert data["files"][1]["name"] == "subdir"
        assert data["files"][1]["is_dir"] is True
        session.list_files.assert_called_once_with("/sandbox")

    @pytest.mark.asyncio
    async def test_read_file_success(self, registered_tools):
        """Reading a text file should return its content."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            # read_image raises → fallback to read_file
            session.read_image.side_effect = RuntimeError("Not an image")
            session.read_file.return_value = b"hello world"
            mock_get_session.return_value = session

            result = await sf_tool(operation="read", path="/sandbox/test.txt")

        data = json.loads(result)
        assert data["ok"] is True
        assert data["content"] == "hello world"
        session.read_file.assert_called_once_with("/sandbox/test.txt")
        session.read_image.assert_called_once_with("/sandbox/test.txt")

    @pytest.mark.asyncio
    async def test_write_file_success(self, registered_tools):
        """Writing a file should return success with stdout."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.execute.return_value = ExecResult(
                stdout="written 11 bytes",
                stderr="",
                exit_code=0,
            )
            mock_get_session.return_value = session

            result = await sf_tool(operation="write", path="/sandbox/test.txt", content="hello world")

        data = json.loads(result)
        assert data["ok"] is True
        assert data["path"] == "/sandbox/test.txt"
        assert "written" in data["stdout"]
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_file_success(self, registered_tools):
        """Deleting a file should succeed."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.delete_file.return_value = True
            mock_get_session.return_value = session

            result = await sf_tool(operation="delete", path="/sandbox/test.txt")

        data = json.loads(result)
        assert data["ok"] is True
        assert data["path"] == "/sandbox/test.txt"
        session.delete_file.assert_called_once_with("/sandbox/test.txt")

    @pytest.mark.asyncio
    async def test_delete_file_failure(self, registered_tools):
        """Deleting a non-existent file should return error."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.delete_file.return_value = False
            mock_get_session.return_value = session

            result = await sf_tool(operation="delete", path="/sandbox/nonexistent.txt")

        data = json.loads(result)
        assert data["ok"] is False
        assert "delete failed" in data["error"]
        session.delete_file.assert_called_once_with("/sandbox/nonexistent.txt")

    @pytest.mark.asyncio
    async def test_read_image_file(self, registered_tools):
        """Reading an image file should return base64 content."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.read_image.return_value = {
                "content_type": "image/png",
                "content_base64": "iVBORw0KGgo=",
                "size": 1024,
            }
            mock_get_session.return_value = session

            result = await sf_tool(operation="read", path="/sandbox/plot.png")

        data = json.loads(result)
        assert data["ok"] is True
        assert data["content_type"] == "image/png"
        assert data["content_base64"] == "iVBORw0KGgo="
        assert data["size"] == 1024
        session.read_image.assert_called_once_with("/sandbox/plot.png")

    @pytest.mark.asyncio
    async def test_read_image_with_resize(self, registered_tools):
        """Reading a resized image should include resize metadata."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)
            session = _mock_sandbox_session()
            session.read_image.return_value = {
                "content_type": "image/jpeg",
                "content_base64": "/9j/4AAQ==",
                "size": 2048,
                "resized": True,
                "orig_dims": "3000x2000",
            }
            mock_get_session.return_value = session

            result = await sf_tool(operation="read", path="/sandbox/photo.jpg")

        data = json.loads(result)
        assert data["ok"] is True
        assert data["resized"] is True
        assert data["orig_dims"] == "3000x2000"
        session.read_image.assert_called_once_with("/sandbox/photo.jpg")

    @pytest.mark.asyncio
    async def test_invalid_operation(self, registered_tools):
        """Invalid operation should return error."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session"),
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)

            result = await sf_tool(operation="invalid")

        data = json.loads(result)
        assert data["ok"] is False
        assert "Unknown operation" in data["error"]

    @pytest.mark.asyncio
    async def test_path_must_be_under_sandbox(self, registered_tools):
        """Path outside /sandbox should be rejected."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session") as mock_get_session,
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)

            result = await sf_tool(operation="list", path="/etc/passwd")

        data = json.loads(result)
        assert data["ok"] is False
        assert "path must be under /sandbox" in data["error"]
        mock_get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_requires_content(self, registered_tools):
        """Write without content should return error."""
        tools, ctx, _ = registered_tools
        sf_tool = tools["sandbox_files"]

        with (
            patch("memory_mcp.config.settings.get_settings") as mock_get_settings,
            patch("memory_mcp.application.sandbox.service.get_sandbox_session"),
        ):
            mock_get_settings.return_value = _mock_settings(enabled=True)

            result = await sf_tool(operation="write", path="/sandbox/test.txt", content=None)

        data = json.loads(result)
        assert data["ok"] is False
        assert "content is required" in data["error"]
