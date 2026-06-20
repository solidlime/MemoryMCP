"""Tests for MCP tool handlers: goal_manage and promise_manage."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.shared.errors import RepositoryError
from memory_mcp.domain.shared.result import Failure, Success

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mem(
    key: str = "mem_001",
    content: str = "test content",
    tags: list[str] | None = None,
) -> Memory:
    now = datetime.now(UTC)
    return Memory(key=key, content=content, created_at=now, updated_at=now, tags=tags or [])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_app_context():
    ctx = MagicMock()
    ctx.memory_service = MagicMock()
    ctx.persona_service = MagicMock()
    ctx.event_bus = AsyncMock()
    return ctx


@pytest.fixture
def registered_tools(mock_app_context):
    """
    Call register_tools with a mock FastMCP, capturing the tool functions
    by intercepting the @mcp.tool() decorator calls.
    """
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


# ===========================================================================
# goal_manage
# ===========================================================================


class TestGoalManage:
    """Tests for goal_manage tool."""

    # -- Create ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_goal(self, registered_tools):
        """Creating a goal should create a memory with ['goal', 'active'] tags."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Success(_mem("goal_001", tags=["goal", "active"]))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="create", content="learn python")

        assert "Goal created: goal_001" in result
        ctx.memory_service.create_memory.assert_called_once_with(
            content="learn python",
            importance=0.75,
            tags=["goal", "active"],
            emotion="neutral",
        )

    @pytest.mark.asyncio
    async def test_create_goal_custom_importance(self, registered_tools):
        """Custom importance should be passed through to create_memory."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Success(_mem("goal_002"))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="create", content="important", importance=0.9)

        assert "Goal created" in result
        ctx.memory_service.create_memory.assert_called_once_with(
            content="important",
            importance=0.9,
            tags=["goal", "active"],
            emotion="neutral",
        )

    @pytest.mark.asyncio
    async def test_create_goal_service_failure(self, registered_tools):
        """Service failure on create should return error message."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Failure(RepositoryError("db error"))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="create", content="test")

        assert "Error" in result

    # -- Achieve ----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_achieve_goal_by_key(self, registered_tools):
        """Achieving a goal by memory_key should update its tags."""
        tools, ctx, _ = registered_tools
        m = _mem("goal_001", content="learn python", tags=["goal", "active"])
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.update_memory.return_value = Success(_mem("goal_001", tags=["goal", "achieved"]))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="achieve", memory_key="goal_001")

        assert "Goal achieved" in result
        assert "learn python" in result
        ctx.memory_service.get_memory.assert_called_once_with("goal_001")
        ctx.memory_service.update_memory.assert_called_once_with(
            "goal_001", importance=0.9, tags=["goal", "achieved", "archived"]
        )

    @pytest.mark.asyncio
    async def test_achieve_goal_by_content(self, registered_tools):
        """Achieving a goal by content matching should find and update the goal."""
        tools, ctx, _ = registered_tools
        m = _mem("goal_001", content="learn python", tags=["goal", "active"])
        ctx.memory_service.get_by_tags.return_value = Success([m])
        ctx.memory_service.update_memory.return_value = Success(_mem("goal_001", tags=["goal", "achieved"]))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="achieve", content="learn python")

        assert "Goal achieved" in result
        assert "learn python" in result
        ctx.memory_service.get_by_tags.assert_called_once_with(["goal", "active"])
        ctx.memory_service.update_memory.assert_called_once_with(
            "goal_001", importance=0.9, tags=["goal", "achieved", "archived"]
        )

    @pytest.mark.asyncio
    async def test_achieve_goal_by_content_case_insensitive(self, registered_tools):
        """Content matching should be case-insensitive."""
        tools, ctx, _ = registered_tools
        m = _mem("goal_001", content="LEARN PYTHON", tags=["goal", "active"])
        ctx.memory_service.get_by_tags.return_value = Success([m])
        ctx.memory_service.update_memory.return_value = Success(_mem("goal_001", tags=["goal", "achieved"]))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="achieve", content="learn python")

        assert "Goal achieved" in result

    @pytest.mark.asyncio
    async def test_achieve_goal_not_active(self, registered_tools):
        """Achieving a memory that is not an active goal should return error."""
        tools, ctx, _ = registered_tools
        m = _mem("goal_001", content="learn python", tags=["goal", "achieved"])
        ctx.memory_service.get_memory.return_value = Success(m)
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="achieve", memory_key="goal_001")

        assert "Error" in result
        assert "not an active goal" in result

    @pytest.mark.asyncio
    async def test_achieve_goal_key_not_found(self, registered_tools):
        """Achieving a goal with non-existent key should return error."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_memory.return_value = Failure(RepositoryError("not found"))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="achieve", memory_key="missing")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_achieve_goal_no_match_by_content(self, registered_tools):
        """Achieving a goal by content when no match exists should return error."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_by_tags.return_value = Success(
            [_mem("goal_001", content="something else", tags=["goal", "active"])]
        )
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="achieve", content="nonexistent")

        assert "Error" in result
        assert "No active goal matching" in result

    @pytest.mark.asyncio
    async def test_achieve_goal_update_failure(self, registered_tools):
        """Service failure on update should return error."""
        tools, ctx, _ = registered_tools
        m = _mem("goal_001", content="learn python", tags=["goal", "active"])
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.update_memory.return_value = Failure(RepositoryError("update failed"))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="achieve", memory_key="goal_001")

        assert "Error" in result

    # -- Cancel -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_cancel_goal_by_key(self, registered_tools):
        """Cancelling a goal by memory_key should update tags to cancelled."""
        tools, ctx, _ = registered_tools
        m = _mem("goal_001", content="learn python", tags=["goal", "active"])
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.update_memory.return_value = Success(_mem("goal_001", tags=["goal", "cancelled"]))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="cancel", memory_key="goal_001")

        assert "Goal cancelled" in result
        assert "learn python" in result
        ctx.memory_service.get_memory.assert_called_once_with("goal_001")
        ctx.memory_service.update_memory.assert_called_once_with(
            "goal_001", importance=0.9, tags=["goal", "cancelled", "archived"]
        )

    @pytest.mark.asyncio
    async def test_cancel_goal_by_content(self, registered_tools):
        """Cancelling a goal by content matching should find and update."""
        tools, ctx, _ = registered_tools
        m = _mem("goal_001", content="learn python", tags=["goal", "active"])
        ctx.memory_service.get_by_tags.return_value = Success([m])
        ctx.memory_service.update_memory.return_value = Success(_mem("goal_001", tags=["goal", "cancelled"]))
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="cancel", content="learn python")

        assert "Goal cancelled" in result
        assert "learn python" in result

    # -- Edge cases -------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_unknown_operation(self, registered_tools):
        """Unknown operation should return error."""
        tools, ctx, _ = registered_tools
        goal_manage = tools["goal_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await goal_manage(operation="invalid")

        assert "Error" in result
        assert "Unknown operation" in result


# ===========================================================================
# promise_manage
# ===========================================================================


class TestPromiseManage:
    """Tests for promise_manage tool."""

    # -- Create ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_promise(self, registered_tools):
        """Creating a promise should create a memory with ['promise', 'active'] tags."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Success(_mem("prom_001", tags=["promise", "active"]))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="create", content="I will help")

        assert "Promise created: prom_001" in result
        ctx.memory_service.create_memory.assert_called_once_with(
            content="I will help",
            importance=0.8,
            tags=["promise", "active"],
            emotion="neutral",
        )

    @pytest.mark.asyncio
    async def test_create_promise_custom_importance(self, registered_tools):
        """Custom importance should be passed through for promise creation."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Success(_mem("prom_002"))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="create", content="important promise", importance=0.95)

        assert "Promise created" in result
        ctx.memory_service.create_memory.assert_called_once_with(
            content="important promise",
            importance=0.95,
            tags=["promise", "active"],
            emotion="neutral",
        )

    @pytest.mark.asyncio
    async def test_create_promise_service_failure(self, registered_tools):
        """Service failure on promise create should return error."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Failure(RepositoryError("db error"))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="create", content="test")

        assert "Error" in result

    # -- Fulfill ---------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_fulfill_promise_by_key(self, registered_tools):
        """Fulfilling a promise by memory_key should update its tags."""
        tools, ctx, _ = registered_tools
        m = _mem("prom_001", content="I will help", tags=["promise", "active"])
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.update_memory.return_value = Success(_mem("prom_001", tags=["promise", "fulfilled"]))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="fulfill", memory_key="prom_001")

        assert "Promise fulfilled" in result
        assert "I will help" in result
        ctx.memory_service.get_memory.assert_called_once_with("prom_001")
        ctx.memory_service.update_memory.assert_called_once_with(
            "prom_001", importance=0.9, tags=["promise", "fulfilled", "archived"]
        )

    @pytest.mark.asyncio
    async def test_fulfill_promise_by_content(self, registered_tools):
        """Fulfilling a promise by content should find and update."""
        tools, ctx, _ = registered_tools
        m = _mem("prom_001", content="I will help", tags=["promise", "active"])
        ctx.memory_service.get_by_tags.return_value = Success([m])
        ctx.memory_service.update_memory.return_value = Success(_mem("prom_001", tags=["promise", "fulfilled"]))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="fulfill", content="I will help")

        assert "Promise fulfilled" in result
        assert "I will help" in result
        ctx.memory_service.get_by_tags.assert_called_once_with(["promise", "active"])

    @pytest.mark.asyncio
    async def test_fulfill_promise_by_content_case_insensitive(self, registered_tools):
        """Content matching for promises should be case-insensitive."""
        tools, ctx, _ = registered_tools
        m = _mem("prom_001", content="I WILL HELP", tags=["promise", "active"])
        ctx.memory_service.get_by_tags.return_value = Success([m])
        ctx.memory_service.update_memory.return_value = Success(_mem("prom_001", tags=["promise", "fulfilled"]))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="fulfill", content="i will help")

        assert "Promise fulfilled" in result

    @pytest.mark.asyncio
    async def test_fulfill_promise_not_active(self, registered_tools):
        """Fulfilling a memory that is not an active promise should return error."""
        tools, ctx, _ = registered_tools
        m = _mem("prom_001", content="I will help", tags=["promise", "fulfilled"])
        ctx.memory_service.get_memory.return_value = Success(m)
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="fulfill", memory_key="prom_001")

        assert "Error" in result
        assert "not an active promise" in result

    @pytest.mark.asyncio
    async def test_fulfill_promise_key_not_found(self, registered_tools):
        """Fulfilling a promise with non-existent key should return error."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_memory.return_value = Failure(RepositoryError("not found"))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="fulfill", memory_key="missing")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_fulfill_promise_no_match_by_content(self, registered_tools):
        """Fulfilling by content when no match exists should return error."""
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_by_tags.return_value = Success(
            [_mem("prom_001", content="something else", tags=["promise", "active"])]
        )
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="fulfill", content="nonexistent promise")

        assert "Error" in result
        assert "No active promise matching" in result

    @pytest.mark.asyncio
    async def test_fulfill_promise_update_failure(self, registered_tools):
        """Service failure on update should return error."""
        tools, ctx, _ = registered_tools
        m = _mem("prom_001", content="I will help", tags=["promise", "active"])
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.update_memory.return_value = Failure(RepositoryError("update failed"))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="fulfill", memory_key="prom_001")

        assert "Error" in result

    # -- Cancel -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_cancel_promise_by_key(self, registered_tools):
        """Cancelling a promise by memory_key should update tags to cancelled."""
        tools, ctx, _ = registered_tools
        m = _mem("prom_001", content="I will help", tags=["promise", "active"])
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.update_memory.return_value = Success(_mem("prom_001", tags=["promise", "cancelled"]))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="cancel", memory_key="prom_001")

        assert "Promise cancelled" in result
        assert "I will help" in result

    @pytest.mark.asyncio
    async def test_cancel_promise_by_content(self, registered_tools):
        """Cancelling a promise by content should find and update."""
        tools, ctx, _ = registered_tools
        m = _mem("prom_001", content="I will help", tags=["promise", "active"])
        ctx.memory_service.get_by_tags.return_value = Success([m])
        ctx.memory_service.update_memory.return_value = Success(_mem("prom_001", tags=["promise", "cancelled"]))
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="cancel", content="I will help")

        assert "Promise cancelled" in result
        assert "I will help" in result

    # -- Edge cases -------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_promise_unknown_operation(self, registered_tools):
        """Unknown operation should return error."""
        tools, ctx, _ = registered_tools
        promise_manage = tools["promise_manage"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await promise_manage(operation="invalid")

        assert "Error" in result
        assert "Unknown operation" in result
