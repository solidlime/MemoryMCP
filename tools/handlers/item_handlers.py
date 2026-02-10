"""Item operation handlers for unified item tool."""

from typing import Optional, List, Dict

# Import equipment operations
from tools.equipment_tools import (
    add_to_inventory as _add_to_inventory,
    remove_from_inventory as _remove_from_inventory,
    equip_item as _equip_item,
    unequip_item as _unequip_item,
    update_item as _update_item,
    rename_item as _rename_item,
    search_inventory as _search_inventory,
    get_equipment_history as _get_equipment_history
)

# Import item-memory analysis
from tools.item_memory_tools import (
    get_memories_with_item as _get_memories_with_item,
    get_item_usage_stats as _get_item_usage_stats
)


async def handle_item_operation(
    operation: str,
    # Common parameters
    item_name: Optional[str] = None,
    # Add/Update parameters
    description: Optional[str] = None,
    quantity: int = 1,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    # Rename parameters
    new_name: Optional[str] = None,
    # Equip/Unequip parameters
    equipment: Optional[Dict[str, str]] = None,
    slots: Optional[List[str] | str] = None,
    # Search parameters
    query: Optional[str] = None,
    # History parameters
    history_slot: Optional[str] = None,
    days: int = 7,
    # Analysis parameters
    mode: str = "memories",
    top_k: int = 10
) -> str:
    """
    Handle item operations.

    Args:
        operation: Operation type - "add", "remove", "equip", "unequip",
                  "update", "rename", "search", "history", "memories", "stats"
        item_name: Item name (required for most operations)
        description: Item description (for add/update)
        quantity: Number of items to add/remove (default: 1)
        category: Item category (e.g., "weapon", "consumable", "clothing")
        tags: List of tags for categorization
        new_name: New item name (for rename operation)
        equipment: Dict mapping slot names to item names (for equip operation)
        slots: Slot name(s) to unequip (string or list, for unequip operation)
        query: Search query string (for search operation)
        history_slot: Equipment slot to get history for (for history operation)
        days: Number of days to look back in history (default: 7)
        mode: Analysis mode (currently "memories")
        top_k: Number of results to return (for memories operation, default: 10)

    Returns:
        Operation result string
    """
    operation = operation.lower()

    if operation == "add":
        if not item_name:
            return "❌ Error: 'item_name' is required for add operation"
        return _add_to_inventory(
            item_name=item_name,
            description=description,
            quantity=quantity,
            category=category or "misc",
            tags=tags
        )

    elif operation == "remove":
        if not item_name:
            return "❌ Error: 'item_name' is required for remove operation"
        return _remove_from_inventory(
            item_name=item_name,
            quantity=quantity
        )

    elif operation == "equip":
        if not equipment:
            return "❌ Error: 'equipment' dict is required for equip operation (e.g., {'weapon': 'Sword'})"
        return _equip_item(equipment=equipment)

    elif operation == "unequip":
        if not slots:
            return "❌ Error: 'slots' is required for unequip operation (string or list)"
        return _unequip_item(slots=slots)

    elif operation == "update":
        if not item_name:
            return "❌ Error: 'item_name' is required for update operation"
        return _update_item(
            item_name=item_name,
            description=description,
            category=category,
            tags=tags
        )

    elif operation == "rename":
        if not item_name:
            return "❌ Error: 'item_name' is required for rename operation"
        if not new_name:
            return "❌ Error: 'new_name' is required for rename operation"
        return _rename_item(
            old_name=item_name,
            new_name=new_name
        )

    elif operation == "search":
        # Allow search without any parameters to list all items
        return _search_inventory(
            query=query,
            category=category,
            tags=tags
        )

    elif operation == "history":
        return _get_equipment_history(
            slot=history_slot,
            days=days
        )

    elif operation == "memories":
        if not item_name:
            return "❌ Error: 'item_name' is required for memories operation"
        return await _get_memories_with_item(
            item_name=item_name,
            slot=None,
            top_k=top_k
        )

    elif operation == "stats":
        if not item_name:
            return "❌ Error: 'item_name' is required for stats operation"
        return await _get_item_usage_stats(item_name=item_name)

    else:
        return f"❌ Error: Unknown operation '{operation}'. Valid: add, remove, equip, unequip, update, rename, search, history, memories, stats"
