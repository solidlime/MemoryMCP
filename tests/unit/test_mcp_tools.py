"""Tests for MCP tool handlers in memory_mcp/api/mcp/tools.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.persona.entities import PersonaState
from memory_mcp.domain.search.engine import SearchResult
from memory_mcp.domain.shared.errors import DomainError, RepositoryError
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
# memory() — create
# ---------------------------------------------------------------------------


class TestMemoryCreate:
    @pytest.mark.asyncio
    async def test_create_success(self, registered_tools):
        tools, ctx, registry = registered_tools
        ctx.memory_service.create_memory.return_value = Success(_mem("mem_new"))

        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="create", content="hello world")

        assert "mem_new" in result
        ctx.memory_service.create_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_requires_content(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="create")
        assert "Error" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_create_invalid_importance(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="create", content="hi", importance=1.5)
        assert "Error" in result
        assert "importance" in result

    @pytest.mark.asyncio
    async def test_create_unknown_emotion_warns(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Success(_mem("mem_x"))
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="create", content="hi", emotion_type="rainbow")
        assert "Warning" in result

    @pytest.mark.asyncio
    async def test_create_service_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.create_memory.return_value = Failure(RepositoryError("db error"))
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="create", content="hi")
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory() — read
# ---------------------------------------------------------------------------


class TestMemoryRead:
    @pytest.mark.asyncio
    async def test_read_by_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        m = _mem("mem_001", "stored content")
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.boost_recall.return_value = Success(None)
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="read", memory_key="mem_001")
        assert "stored content" in result
        assert "mem_001" in result

    @pytest.mark.asyncio
    async def test_read_recent_when_no_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_recent.return_value = Success([_mem("k1"), _mem("k2")])
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="read")
        assert "k1" in result
        assert "k2" in result

    @pytest.mark.asyncio
    async def test_read_by_key_not_found(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_memory.return_value = Failure(RepositoryError("not found"))
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="read", memory_key="missing")
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory() — delete
# ---------------------------------------------------------------------------


class TestMemoryDelete:
    @pytest.mark.asyncio
    async def test_delete_by_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        m = _mem("mem_del")
        ctx.memory_service.get_memory.return_value = Success(m)
        ctx.memory_service.delete_memory.return_value = Success(None)
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="delete", memory_key="mem_del")
        assert "deleted" in result.lower()

    @pytest.mark.asyncio
    async def test_delete_requires_key_or_query(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="delete")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_delete_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_memory.return_value = Failure(RepositoryError("not found"))
        ctx.memory_service.delete_memory.return_value = Failure(RepositoryError("not found"))
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="delete", memory_key="missing")
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory() — stats
# ---------------------------------------------------------------------------


class TestMemoryStats:
    @pytest.mark.asyncio
    async def test_stats_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_stats.return_value = Success({"total": 42, "by_emotion": {}})
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="stats")
        assert "42" in result

    @pytest.mark.asyncio
    async def test_stats_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.get_stats.return_value = Failure(RepositoryError("db error"))
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="stats")
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory() — update
# ---------------------------------------------------------------------------


class TestMemoryUpdate:
    @pytest.mark.asyncio
    async def test_update_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.update_memory.return_value = Success(_mem("mem_001"))
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="update", memory_key="mem_001", content="new content")
        assert "updated" in result.lower()

    @pytest.mark.asyncio
    async def test_update_requires_key(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="update")
        assert "Error" in result
        assert "memory_key" in result

    @pytest.mark.asyncio
    async def test_update_invalid_importance(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="update", memory_key="k1", importance=-0.1)
        assert "Error" in result


# ---------------------------------------------------------------------------
# memory() — block operations
# ---------------------------------------------------------------------------


class TestMemoryBlocks:
    @pytest.mark.asyncio
    async def test_block_write_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.write_block.return_value = Success(None)
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="block_write", block_name="myblock", content="block content")
        assert "written" in result.lower()

    @pytest.mark.asyncio
    async def test_block_write_missing_params(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="block_write", block_name="b")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_block_read_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.read_block.return_value = Success("block data here")
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="block_read", block_name="myblock")
        assert "block data here" in result

    @pytest.mark.asyncio
    async def test_block_list(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.list_blocks.return_value = Success([{"block_name": "b1", "content": "data"}])
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="block_list")
        assert result  # should return something

    @pytest.mark.asyncio
    async def test_block_delete_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.memory_service.delete_block.return_value = Success(None)
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="block_delete", block_name="myblock")
        assert "deleted" in result.lower()


# ---------------------------------------------------------------------------
# memory() — unknown operation
# ---------------------------------------------------------------------------


class TestMemoryUnknownOperation:
    @pytest.mark.asyncio
    async def test_unknown_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        memory = tools["memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await memory(operation="fly_to_moon")
        assert "Unknown operation" in result


# ---------------------------------------------------------------------------
# search_memory()
# ---------------------------------------------------------------------------


class TestSearchMemory:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, registered_tools):
        tools, ctx, _ = registered_tools
        sr = _search_result("mem_abc", score=0.75)
        ctx.search_engine.search.return_value = Success([sr])
        ctx.memory_service.log_search.return_value = Success(None)
        # search_engine._semantic should exist for the persona assignment
        ctx.search_engine._semantic = None
        search_memory = tools["search_memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await search_memory(query="test query")
        assert "mem_abc" in result
        assert "0.750" in result

    @pytest.mark.asyncio
    async def test_search_no_results(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.search_engine.search.return_value = Success([])
        ctx.search_engine._semantic = None
        search_memory = tools["search_memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await search_memory(query="nothing")
        assert "No results" in result

    @pytest.mark.asyncio
    async def test_search_invalid_top_k(self, registered_tools):
        tools, ctx, _ = registered_tools
        search_memory = tools["search_memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await search_memory(query="test", top_k=0)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_search_engine_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        from memory_mcp.domain.shared.errors import SearchError
        ctx.search_engine.search.return_value = Failure(SearchError("vector store down"))
        ctx.search_engine._semantic = None
        search_memory = tools["search_memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await search_memory(query="test")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_search_passes_tags_and_filters(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.search_engine.search.return_value = Success([])
        ctx.search_engine._semantic = None
        ctx.memory_service.log_search.return_value = Success(None)
        search_memory = tools["search_memory"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            await search_memory(
                query="test",
                mode="keyword",
                top_k=3,
                tags=["goal"],
                min_importance=0.7,
                emotion="joy",
                importance_weight=0.5,
                recency_weight=0.3,
            )
        call_args = ctx.search_engine.search.call_args[0][0]
        assert call_args.mode == "keyword"
        assert call_args.top_k == 3
        assert call_args.tags == ["goal"]
        assert call_args.min_importance == 0.7
        assert call_args.emotion == "joy"
        assert call_args.importance_weight == 0.5
        assert call_args.recency_weight == 0.3


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
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await update_context(emotion="joy", emotion_intensity=0.9)
        assert "emotion=joy" in result
        ctx.persona_service.update_emotion.assert_called_once_with("test_persona", "joy", 0.9)

    @pytest.mark.asyncio
    async def test_update_physical_state(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.update_physical_state.return_value = Success(None)
        update_context = tools["update_context"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
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
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
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
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
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
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
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
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
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
        ctx.equipment_service.get_equipment.return_value = Success({})
        ctx.memory_service.list_blocks.return_value = Success([])
        ctx.memory_service.get_by_tags.return_value = Success([])
        ctx.memory_service.get_recent_searches.return_value = Success([])
        ctx.memory_service.count_decayed_important.return_value = Success(0)
        ctx.memory_service.get_memory_index.return_value = Success(None)
        ctx.memory_service.get_relationship_highlights.return_value = Success([])
        ctx.persona_service.record_conversation_time.return_value = Success(None)
        get_context = tools["get_context"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await get_context()
        assert "test_persona" in result
        assert "joy" in result

    @pytest.mark.asyncio
    async def test_get_context_persona_service_failure(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.persona_service.get_context.return_value = Failure(DomainError("persona error"))
        get_context = tools["get_context"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
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
        ctx.equipment_service.get_equipment.return_value = Success({})
        ctx.memory_service.list_blocks.return_value = Success([])
        ctx.memory_service.get_by_tags.side_effect = lambda tags: (
            Success([goal_mem]) if "goal" in tags else Success([])
        )
        ctx.memory_service.get_recent_searches.return_value = Success([])
        ctx.memory_service.count_decayed_important.return_value = Success(0)
        ctx.memory_service.get_memory_index.return_value = Success(None)
        ctx.memory_service.get_relationship_highlights.return_value = Success([])
        ctx.persona_service.record_conversation_time.return_value = Success(None)
        get_context = tools["get_context"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await get_context()
        assert "Finish project" in result


# ---------------------------------------------------------------------------
# item()
# ---------------------------------------------------------------------------


class TestItemTool:
    @pytest.mark.asyncio
    async def test_equip_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.equip.return_value = Success(None)
        item = tools["item"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item(operation="equip", equipment={"top": "white dress"})
        assert "Equipped" in result
        ctx.equipment_service.equip.assert_called_once_with({"top": "white dress"}, True)

    @pytest.mark.asyncio
    async def test_equip_missing_equipment(self, registered_tools):
        tools, ctx, _ = registered_tools
        item = tools["item"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item(operation="equip")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_add_item(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.add_item.return_value = Success(None)
        item = tools["item"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item(operation="add", item_name="blue hat", category="accessories")
        assert "added" in result.lower()

    @pytest.mark.asyncio
    async def test_remove_item(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.remove_item.return_value = Success(None)
        item = tools["item"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item(operation="remove", item_name="blue hat")
        assert "removed" in result.lower()

    @pytest.mark.asyncio
    async def test_unequip_slots(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.unequip.return_value = Success(None)
        item = tools["item"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item(operation="unequip", slots=["top", "head"])
        assert "Unequipped" in result

    @pytest.mark.asyncio
    async def test_search_items(self, registered_tools):
        tools, ctx, _ = registered_tools
        item_obj = MagicMock()
        item_obj.name = "blue hat"
        item_obj.category = "accessories"
        item_obj.quantity = 1
        ctx.equipment_service.search_items.return_value = Success([item_obj])
        item = tools["item"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item(operation="search", query="hat")
        assert "blue hat" in result

    @pytest.mark.asyncio
    async def test_unknown_item_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        item = tools["item"]
        with (
            patch("memory_mcp.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("memory_mcp.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item(operation="fly")
        assert "Unknown operation" in result
