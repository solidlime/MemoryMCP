# Changelog

All notable changes to Memory-MCP will be documented in this file.

## [Unreleased]

### Changed - 2025-11-17 (Equipment Tools Enhancement)

#### Equipment System Improvements

Enhanced equipment management with more flexible unequip and equip operations.

**Changes:**
1. **`unequip_item()` enhancement**:
   - Now accepts single slot or list of slots
   - Can unequip multiple items at once
   - Example: `unequip_item(["top", "foot"])` or `unequip_item("weapon")`

2. **`equip_item()` behavior change**:
   - No longer automatically unequips all equipment
   - Only equips specified slots
   - More granular control over equipment changes
   - Example: `equip_item({"top": "White Dress"})` keeps other slots equipped

3. **Type hints consistency**:
   - Unified to use `Optional[...]`, `List[...]`, `Dict[...]` style
   - Improved code readability and IDE support

**Migration:**
- Old: `equip_item({...})` auto-unequipped everything → Now: only affects specified slots
- To unequip all: Use `item(operation="equip", equipment={})` in unified tool

**Files Changed:**
- `tools/equipment_tools.py`: Updated `equip_item()` and `unequip_item()` signatures
- `core/equipment_db.py`: Improved type hints

### Changed - 2025-11-16 (Phase 35: Tool Consolidation)

#### Tool Count Reduction (75% reduction: 12 → 3 tools)

Consolidated individual memory and item operations into unified tools to significantly reduce context consumption.

**Before (12 tools):**
- Memory operations: `create_memory`, `update_memory`, `search_memory`, `delete_memory`
- Item operations: `add_to_inventory`, `remove_from_inventory`, `equip_item`, `update_item`, `search_inventory`, `get_equipment_history`, `analyze_item`
- Context: `get_context`

**After (3 tools):**
- **`memory`**: Unified memory interface (operations: create, read, update, delete, search, stats)
- **`item`**: Unified item interface (operations: add, remove, equip, update, search, history, memories, stats)
- **`get_context`**: Unchanged

**Benefits:**
- 75% reduction in tool count (12 → 3)
- Estimated 70-80% reduction in context size
- Simplified API with consistent operation-based interface
- All existing functionality preserved

**Migration Examples:**

```python
# Old way
create_memory(content="User likes strawberry", emotion_type="joy")
search_inventory(category="weapon")

# New way (unified interface)
memory(operation="create", content="User likes strawberry", emotion_type="joy")
item(operation="search", category="weapon")
```

**Files Changed:**
- Added: `tools/unified_tools.py` - Unified tool implementation
- Modified: `tools_memory.py` - Updated tool registration
- Modified: `tools/item_memory_tools.py` - Deprecated `analyze_item`

**Backward Compatibility:**
- All operations available through unified interface
- Internal implementation reuses existing functions
- No breaking changes to functionality

---

## Previous Changes

See git history for earlier changes.
