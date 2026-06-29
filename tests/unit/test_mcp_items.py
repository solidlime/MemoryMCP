"""Tests for item-related MCP tool handlers (equip, add, remove, unequip, search, update)."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nous.domain.shared.errors import RepositoryError
from nous.domain.shared.result import Failure, Success

UTC = UTC


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
# item_add, item_remove, item_equip, item_unequip, item_update, item_search, item_history
# ---------------------------------------------------------------------------


class TestItemTool:
    @pytest.mark.asyncio
    async def test_equip_success(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.equip.return_value = Success(None)
        item_equip = tools["item_equip"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_equip(equipment={"top": "white dress"})
        assert "Equipped" in result
        ctx.equipment_service.equip.assert_called_once_with({"top": "white dress"}, True)

    @pytest.mark.asyncio
    async def test_equip_missing_equipment(self, registered_tools):
        tools, ctx, _ = registered_tools
        item_equip = tools["item_equip"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_equip()
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_add_item(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.add_item.return_value = Success(None)
        item_add = tools["item_add"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_add(item_name="blue hat", category="accessories")
        assert "added" in result.lower()

    @pytest.mark.asyncio
    async def test_remove_item(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.remove_item.return_value = Success(None)
        item_remove = tools["item_remove"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_remove(item_name="blue hat")
        assert "removed" in result.lower()

    @pytest.mark.asyncio
    async def test_unequip_slots(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.unequip.return_value = Success(None)
        item_unequip = tools["item_unequip"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_unequip(slots=["top", "head"])
        assert "Unequipped" in result

    @pytest.mark.asyncio
    async def test_search_items(self, registered_tools):
        tools, ctx, _ = registered_tools
        item_obj = MagicMock()
        item_obj.name = "blue hat"
        item_obj.category = "accessories"
        item_obj.quantity = 1
        ctx.equipment_service.search_items.return_value = Success([item_obj])
        item_search = tools["item_search"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_search(query="hat")
        assert "blue hat" in result

    @pytest.mark.asyncio
    async def test_update_item(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.update_item.return_value = Success(None)
        item_update = tools["item_update"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_update(item_name="blue hat", quantity=3)
        assert "updated" in result.lower()


class TestItemHistory:
    """Tests for item_history tool."""

    @pytest.mark.asyncio
    async def test_history_success(self, registered_tools):
        """Getting equipment history should return recent changes."""
        tools, ctx, _ = registered_tools
        h1 = MagicMock()
        h1.timestamp = "2024-01-15 10:00:00"
        h1.action = "equip"
        h1.item_name = "white dress"
        h1.slot = "top"
        h2 = MagicMock()
        h2.timestamp = "2024-01-15 09:00:00"
        h2.action = "add"
        h2.item_name = "blue hat"
        h2.slot = "accessories"
        ctx.equipment_service.get_history.return_value = Success([h1, h2])
        item_history = tools["item_history"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_history(days=7)
        assert "[2024-01-15 10:00:00] equip: white dress (top)" in result
        assert "[2024-01-15 09:00:00] add: blue hat (accessories)" in result

    @pytest.mark.asyncio
    async def test_history_custom_days(self, registered_tools):
        """Should accept custom days parameter."""
        tools, ctx, _ = registered_tools
        h = MagicMock()
        h.timestamp = "2024-01-15 10:00:00"
        h.action = "equip"
        h.item_name = "white dress"
        h.slot = "top"
        ctx.equipment_service.get_history.return_value = Success([h])
        item_history = tools["item_history"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_history(days=30)
        assert "white dress" in result
        ctx.equipment_service.get_history.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_history_empty(self, registered_tools):
        """Empty history should show appropriate message."""
        tools, ctx, _ = registered_tools
        ctx.equipment_service.get_history.return_value = Success([])
        item_history = tools["item_history"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_history(days=7)
        assert "No history found" in result

    @pytest.mark.asyncio
    async def test_history_service_failure(self, registered_tools):
        """Service failure should return error message."""
        tools, ctx, _ = registered_tools
        ctx.equipment_service.get_history.return_value = Failure(RepositoryError("db error"))
        item_history = tools["item_history"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_history(days=7)
        assert "Error" in result
        assert "db error" in result


# ---------------------------------------------------------------------------
# Unified item tool (operation-based dispatch)
# ---------------------------------------------------------------------------


class TestUnifiedItemTool:
    """Tests for the unified item(operation=...) tool."""

    @pytest.mark.asyncio
    async def test_item_add_via_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.add_item.return_value = Success(None)
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="add", item_name="red shoes", category="shoes")
        assert "added" in result.lower()
        ctx.equipment_service.add_item.assert_called_once_with("red shoes", "shoes", None, 1, None)

    @pytest.mark.asyncio
    async def test_item_remove_via_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.remove_item.return_value = Success(None)
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="remove", item_name="red shoes")
        assert "removed" in result.lower()

    @pytest.mark.asyncio
    async def test_item_equip_via_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.equip.return_value = Success(None)
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="equip", equipment={"top": "red dress"})
        assert "Equipped" in result

    @pytest.mark.asyncio
    async def test_item_unequip_via_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.unequip.return_value = Success(None)
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="unequip", slots=["top"])
        assert "Unequipped" in result

    @pytest.mark.asyncio
    async def test_item_update_via_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        ctx.equipment_service.update_item.return_value = Success(None)
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="update", item_name="red shoes", quantity=3)
        assert "updated" in result.lower()

    @pytest.mark.asyncio
    async def test_item_search_via_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        item_obj = MagicMock()
        item_obj.name = "red shoes"
        item_obj.category = "shoes"
        item_obj.quantity = 1
        ctx.equipment_service.search_items.return_value = Success([item_obj])
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="search", query="shoes")
        assert "red shoes" in result

    @pytest.mark.asyncio
    async def test_item_history_via_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        h = MagicMock()
        h.timestamp = "2024-01-15 10:00:00"
        h.action = "equip"
        h.item_name = "red shoes"
        h.slot = "shoes"
        ctx.equipment_service.get_history.return_value = Success([h])
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="history", days=7)
        assert "red shoes" in result

    @pytest.mark.asyncio
    async def test_item_unknown_operation(self, registered_tools):
        tools, ctx, _ = registered_tools
        item_tool = tools["item"]
        with (
            patch("nous.api.mcp.tools.AppContextRegistry") as mock_reg_cls,
            patch("nous.api.mcp.tools.get_current_persona", return_value="test_persona"),
        ):
            mock_reg_cls.get.return_value = ctx
            result = await item_tool(operation="unknown_op")
        assert "Error" in result
        assert "unknown" in result.lower()
