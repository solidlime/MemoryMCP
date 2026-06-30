"""Tests for context-related MCP tool handlers (update_context, get_context)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nous.domain.memory.entities import Memory
from nous.domain.persona.entities import PersonaState
from nous.domain.search.engine import SearchResult
from nous.domain.shared.errors import DomainError
from nous.domain.shared.result import Failure, Success

UTC = UTC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mem(key: str = "mem_001", content: str = "test content") -> Memory:
    now = datetime.now(UTC)
    return Memory(key=key, content=content, created_at=now, updated_at=now)


def _search_result(key: str = "mem_001", score: float = 0.8) -> SearchResult:
    return SearchResult(memory=_mem(key), score=score, source="keyword")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_app_context():
    ctx = MagicMock()
    ctx.memory_service = MagicMock()
    ctx.search_engine = MagicMock()
    ctx.persona_service = MagicMock()
    ctx.entity_service = MagicMock()
    ctx.event_bus = AsyncMock()
    ctx.vector_store = None  # no Qdrant by default
    ctx.settings = MagicMock()
    ctx.settings.contradiction_threshold = 0.85
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
        patch("nous.api.mcp.tools.AppContextRegistry") as mock_registry_cls,
        patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
    ):
        mock_registry_cls.get.return_value = mock_app_context

        from nous.api.mcp.tools import register_tools

        register_tools(mock_mcp)

        # Yield both the tools dict and the patched context so tests can
        # configure return values.
        yield tools, mock_app_context, mock_registry_cls


# ---------------------------------------------------------------------------
# update_context()
# ---------------------------------------------------------------------------


class TestUpdateContext:
    @pytest.mark.asyncio
    async def test_update_emotion(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.update_emotion.return_value = Success(None)
        update_context = tools["update_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await update_context(emotion="joy", emotion_intensity=0.9)
        assert "emotion=joy" in result
        ctx.persona_service.update_emotion.assert_called_once_with("test_persona", "joy", 0.9, context="manual_update")

    @pytest.mark.asyncio
    async def test_update_physical_state(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.update_physical_state.return_value = Success(None)
        update_context = tools["update_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await update_context(physical_state="tired", mental_state="focused")
        assert "physical_state" in result
        assert "mental_state" in result

    @pytest.mark.asyncio
    async def test_update_no_changes(self, registered_tools):
        tools, ctx, _ = registered_tools
        update_context = tools["update_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await update_context()
        assert "No changes" in result

    @pytest.mark.asyncio
    async def test_update_relationship_status(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.update_relationship.return_value = Success(None)
        update_context = tools["update_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await update_context(relationship_status="friends")
        assert "relationship=friends" in result

    @pytest.mark.asyncio
    async def test_update_nickname_shortcut(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.update_persona_info.return_value = Success(None)
        update_context = tools["update_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await update_context(nickname="Taro")
        assert "nickname=Taro" in result

    @pytest.mark.asyncio
    async def test_update_user_info(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.update_user_info.return_value = Success(None)
        update_context = tools["update_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await update_context(user_info={"name": "Alice", "nickname": "Ali"})
        assert "user_info updated" in result


# ---------------------------------------------------------------------------
# get_context()
# ---------------------------------------------------------------------------


class TestGetContext:
    @pytest.mark.asyncio
    async def test_get_context_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        state = PersonaState(persona="test_persona", emotion="joy", emotion_intensity=0.8)
        ctx.persona_service.get_context.return_value = Success(state)
        ctx.memory_service.get_stats.return_value = Success({"total": 10})
        ctx.memory_service.get_smart_recent.return_value = Success([])
        ctx.memory_service.list_blocks.return_value = Success([])
        ctx.memory_service.get_by_tags.return_value = Success([])
        ctx.memory_service.get_recent_searches.return_value = Success([])
        ctx.memory_service.count_decayed_important.return_value = Success(0)
        ctx.memory_service.get_memory_index.return_value = Success(None)
        ctx.memory_service.get_relationship_highlights.return_value = Success([])
        ctx.persona_service.record_conversation_time.return_value = Success(None)
        get_context = tools["get_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await get_context()
        assert "test_persona" in result
        assert "CURRENT STATE" in result
        assert "joy" in result

    @pytest.mark.asyncio
    async def test_get_context_persona_service_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.get_context.return_value = Failure(DomainError("persona error"))
        get_context = tools["get_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await get_context()
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_get_context_shows_active_goals(self, registered_tools):
        tools, ctx, _ = registered_tools
        state = PersonaState(persona="test_persona")
        goal_mem = _mem("goal_001", "Finish project")
        goal_mem.tags = ["goal", "active"]
        ctx.persona_service.get_context.return_value = Success(state)
        ctx.memory_service.get_stats.return_value = Success({})
        ctx.memory_service.get_smart_recent.return_value = Success([])
        ctx.memory_service.list_blocks.return_value = Success([])
        ctx.memory_service.get_by_tags.side_effect = lambda tags: Success([goal_mem]) if "goal" in tags else Success([])
        ctx.memory_service.get_recent_searches.return_value = Success([])
        ctx.memory_service.count_decayed_important.return_value = Success(0)
        ctx.memory_service.get_memory_index.return_value = Success(None)
        ctx.memory_service.get_relationship_highlights.return_value = Success([])
        ctx.persona_service.record_conversation_time.return_value = Success(None)
        get_context = tools["get_context"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await get_context()
        assert "Finish project" in result
