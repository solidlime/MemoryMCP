"""Tests for memory-related MCP tool handlers (create, read, delete, stats, update, search)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.search.engine import SearchResult
from memory_mcp.domain.shared.errors import RepositoryError
from memory_mcp.domain.shared.result import Failure, Success

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
    ctx.equipment_service = MagicMock()
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
        patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_registry_cls,
        patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
    ):
        mock_registry_cls.get.return_value = mock_app_context

        from memory_mcp.api.mcp.tools import register_tools

        register_tools(mock_mcp)

        # Yield both the tools dict and the patched context so tests can
        # configure return values.
        yield tools, mock_app_context, mock_registry_cls


# ---------------------------------------------------------------------------
# memory_create()
# ---------------------------------------------------------------------------


class TestMemoryCreate:
    @pytest.mark.asyncio
    async def test_create_success(self, registered_tools):
        tools, ctx, registry = registered_tools
        ctx.memory_service.create_memory.return_value = Success(_mem("mem_new"))
        ctx.persona_service.get_state_snapshot.return_value = ("neutral", 0.0, {}, None)

        memory_create = tools["memory_create"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_create(content="hello world")

        assert "mem_new" in result
        ctx.memory_service.create_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_requires_content(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory_create = tools["memory_create"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_create()
        assert "Error" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_create_invalid_importance(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory_create = tools["memory_create"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_create(content="hi", importance=1.5)
        assert "Error" in result
        assert "importance" in result

    @pytest.mark.asyncio
    async def test_create_unknown_emotion_warns(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.get_state_snapshot.return_value = ("neutral", 0.0, {}, None)
        ctx.memory_service.create_memory.return_value = Success(_mem("mem_x"))
        memory_create = tools["memory_create"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_create(content="hi", tags=["test"], defer_vector=True)
        assert "mem_x" in result

    @pytest.mark.asyncio
    async def test_create_service_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.get_state_snapshot.return_value = ("neutral", 0.0, {}, None)
        ctx.memory_service.create_memory.return_value = Failure(RepositoryError("db error"))
        memory_create = tools["memory_create"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_create(content="hi")
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory_read()
# ---------------------------------------------------------------------------


class TestMemoryRead:
    @pytest.mark.asyncio
    async def test_read_by_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        m = _mem("mem_001", "stored content")
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.boost_recall.return_value = Success(None)
        memory_read = tools["memory_read"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_read(memory_key="mem_001")
        assert "stored content" in result
        assert "mem_001" in result

    @pytest.mark.asyncio
    async def test_read_recent_when_no_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_recent.return_value = Success([_mem("k1"), _mem("k2")])
        memory_read = tools["memory_read"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_read()
        assert "k1" in result
        assert "k2" in result

    @pytest.mark.asyncio
    async def test_read_by_key_not_found(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_memory.return_value = Failure(RepositoryError("not found"))
        memory_read = tools["memory_read"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_read(memory_key="missing")
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory_delete()
# ---------------------------------------------------------------------------


class TestMemoryDelete:
    @pytest.mark.asyncio
    async def test_delete_by_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        m = _mem("mem_del")
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.delete_memory.return_value = Success(None)
        memory_delete = tools["memory_delete"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_delete(memory_key="mem_del")
        assert "deleted" in result.lower()

    @pytest.mark.asyncio
    async def test_delete_requires_key_or_query(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory_delete = tools["memory_delete"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_delete()
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_delete_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_memory.return_value = Failure(RepositoryError("not found"))
        ctx.memory_service.delete_memory.return_value = Failure(RepositoryError("not found"))
        memory_delete = tools["memory_delete"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_delete(memory_key="missing")
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory_stats()
# ---------------------------------------------------------------------------


class TestMemoryStats:
    @pytest.mark.asyncio
    async def test_stats_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_stats.return_value = Success({"total": 42, "by_emotion": {}})
        memory_stats = tools["memory_stats"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_stats()
        assert "42" in result

    @pytest.mark.asyncio
    async def test_stats_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_stats.return_value = Failure(RepositoryError("db error"))
        memory_stats = tools["memory_stats"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_stats()
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory_update()
# ---------------------------------------------------------------------------


class TestMemoryUpdate:
    @pytest.mark.asyncio
    async def test_update_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.update_memory.return_value = Success(_mem("mem_001"))
        memory_update = tools["memory_update"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_update(memory_key="mem_001", content="new content")
        assert "updated" in result.lower()

    @pytest.mark.asyncio
    async def test_update_requires_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory_update = tools["memory_update"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_update()
        assert "Error" in result
        assert "memory_key" in result

    @pytest.mark.asyncio
    async def test_update_invalid_importance(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory_update = tools["memory_update"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_update(memory_key="k1", importance=-0.1)
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory_search()
# ---------------------------------------------------------------------------


class TestMemorySearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, registered_tools):
        tools, ctx, _ = registered_tools
        sr = _search_result("mem_abc", score=0.75)
        ctx.search_engine.search.return_value = Success([sr])
        ctx.memory_service.log_search.return_value = Success(None)
        # search_engine._semantic should exist for the persona assignment
        ctx.search_engine._semantic = None
        memory_search = tools["memory_search"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_search(query="test query")
        assert "mem_abc" in result
        assert "0.750" in result

    @pytest.mark.asyncio
    async def test_search_no_results(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.search_engine.search.return_value = Success([])
        ctx.search_engine._semantic = None
        memory_search = tools["memory_search"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_search(query="nothing")
        assert "No results" in result

    @pytest.mark.asyncio
    async def test_search_invalid_top_k(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory_search = tools["memory_search"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_search(query="test", top_k=0)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_search_engine_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        from memory_mcp.domain.shared.errors import SearchError

        ctx.search_engine.search.return_value = Failure(SearchError("vector store down"))
        ctx.search_engine._semantic = None
        memory_search = tools["memory_search"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory_search(query="test")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_search_passes_tags_and_filters(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.search_engine.search.return_value = Success([])
        ctx.search_engine._semantic = None
        ctx.memory_service.log_search.return_value = Success(None)
        memory_search = tools["memory_search"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            await memory_search(
                query="test",
                top_k=3,
                tags=["goal"],
                min_importance=0.7,
                emotion="joy",
                importance_weight=0.5,
                recency_weight=0.3,
            )
        call_args = ctx.search_engine.search.call_args[0][0]
        assert call_args.mode == "hybrid"  # mode is now always hybrid
        assert call_args.top_k == 3
        assert call_args.tags == ["goal"]
        assert call_args.min_importance == 0.7
        assert call_args.emotion == "joy"
        assert call_args.importance_weight == 0.5
        assert call_args.recency_weight == 0.3
