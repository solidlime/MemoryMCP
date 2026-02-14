"""
Unified Tool Interface for Memory-MCP
Consolidates multiple operations into single tools with operation parameter.

This reduces context consumption by minimizing the number of exposed tools.
Refactored for better maintainability and separation of concerns.
"""

from typing import Optional, List, Dict

from core import update_last_conversation_time
from src.utils.persona_utils import get_current_persona
from tools.handlers.memory_handlers import handle_memory_operation
from tools.handlers.context_handlers import handle_context_operation
from tools.handlers.item_handlers import handle_item_operation


async def memory(
    operation: str,
    # Common parameters
    query: Optional[str] = None,
    content: Optional[str] = None,
    top_k: int = 5,
    # Context parameters
    emotion_type: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
    context_tags: Optional[List[str]] = None,
    importance: Optional[float] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    environment: Optional[str] = None,
    user_info: Optional[Dict] = None,
    persona_info: Optional[Dict] = None,
    relationship_status: Optional[str] = None,
    action_tag: Optional[str] = None,
    # Physical sensations parameters (for update_context)
    arousal: Optional[float] = None,
    heart_rate: Optional[str] = None,
    fatigue: Optional[float] = None,
    warmth: Optional[float] = None,
    touch_response: Optional[str] = None,
    # Search-specific parameters
    mode: str = "hybrid",
    fuzzy_match: bool = False,
    fuzzy_threshold: int = 70,
    search_tags: Optional[List[str]] = None,
    tag_match_mode: str = "any",
    date_range: Optional[str] = None,
    min_importance: Optional[float] = None,
    equipped_item: Optional[str] = None,
    importance_weight: float = 0.0,
    recency_weight: float = 0.0,
    memory_key: Optional[str] = None,
    # Privacy & save control parameters
    privacy_level: Optional[str] = None,
    defer_vector: bool = False
) -> str:
    """
    Unified memory operations interface.

    Args:
        operation: Operation type (see below)
        query: Search query or memory key
        content: Memory content or context value
        privacy_level: "public", "internal" (default), "private", "secret"
        defer_vector: If True, skip vector indexing on save

    Memory Operations:
        - "create": Create new memory
        - "read": Retrieve memory by key or recent memories
        - "update": Update existing memory
        - "delete": Delete memory
        - "search": Search memories (keyword/semantic/hybrid/related/smart)
        - "stats": Get memory statistics
        - "check_routines": Find recurring patterns at current time

    Context Operations:
        - "promise": Update/clear active promise
        - "goal": Update/clear current goal
        - "favorite": Add to favorites
        - "preference": Update preferences
        - "anniversary": Manage anniversaries
        - "sensation": Update physical sensations
        - "emotion_flow": Record emotion change
        - "situation_context": Analyze current situation
        - "update_context": Batch update multiple fields

    Examples:
        # Memory operations
        memory(operation="create", content="Completed project", emotion_type="joy")
        memory(operation="read", query="memory_20251210123456")
        memory(operation="search", query="Python", mode="semantic")
        memory(operation="check_routines")

        # Context operations
        memory(operation="promise", content="週末に買い物")
        memory(operation="anniversary", content="結婚記念日",
               persona_info={"date": "2025-11-10"})
    """
    # Update last conversation time for all operations
    update_last_conversation_time(get_current_persona())

    operation = operation.lower()

    # Route to appropriate handler
    # Memory operations
    memory_operations = ["create", "read", "update", "delete", "search", "stats", "check_routines"]
    context_operations = ["promise", "goal", "favorite", "preference", "anniversary",
                         "sensation", "emotion_flow", "situation_context", "update_context"]

    if operation in memory_operations:
        return await handle_memory_operation(
            operation=operation,
            query=query,
            content=content,
            top_k=top_k,
            emotion_type=emotion_type,
            emotion_intensity=emotion_intensity,
            context_tags=context_tags,
            importance=importance,
            physical_state=physical_state,
            mental_state=mental_state,
            environment=environment,
            user_info=user_info,
            persona_info=persona_info,
            relationship_status=relationship_status,
            action_tag=action_tag,
            mode=mode,
            fuzzy_match=fuzzy_match,
            fuzzy_threshold=fuzzy_threshold,
            search_tags=search_tags,
            tag_match_mode=tag_match_mode,
            date_range=date_range,
            min_importance=min_importance,
            equipped_item=equipped_item,
            importance_weight=importance_weight,
            recency_weight=recency_weight,
            memory_key=memory_key,
            privacy_level=privacy_level,
            defer_vector=defer_vector
        )

    # Context operations
    if operation in context_operations:
        # Merge top-level parameters into persona_info for easier handling
        merged_persona_info = persona_info.copy() if persona_info else {}
        merged_user_info = user_info.copy() if user_info else {}

        # Merge direct context parameters
        if physical_state is not None:
            merged_persona_info['physical_state'] = physical_state
        if mental_state is not None:
            merged_persona_info['mental_state'] = mental_state
        if environment is not None:
            merged_persona_info['environment'] = environment
        if relationship_status is not None:
            merged_persona_info['relationship_status'] = relationship_status
        if action_tag is not None:
            merged_persona_info['action_tag'] = action_tag

        # Merge physical sensations into a nested dict
        sensations = {}
        if arousal is not None:
            sensations['arousal'] = arousal
        if heart_rate is not None:
            sensations['heart_rate'] = heart_rate
        if fatigue is not None:
            sensations['fatigue'] = fatigue
        if warmth is not None:
            sensations['warmth'] = warmth
        if touch_response is not None:
            sensations['touch_response'] = touch_response

        if sensations:
            merged_persona_info['physical_sensations'] = sensations

        # Pass both merged_persona_info and merged_user_info
        return await handle_context_operation(
            operation=operation,
            query=query,
            content=content,
            emotion_type=emotion_type,
            emotion_intensity=emotion_intensity,
            persona_info=merged_persona_info,
            user_info=merged_user_info,
            importance=importance
        )

    # Unknown operation
    return (f"❌ Error: Unknown operation '{operation}'. "
            f"Valid memory ops: {', '.join(sorted(memory_operations))}. "
            f"Valid context ops: {', '.join(sorted(context_operations))}")


async def item(
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
    auto_add: bool = True,
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
    Unified item operations interface.

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

    Usage Guidelines:
        ✅ ADD to item inventory:
            - Physical items that can be equipped or carried
            - Categories: 'clothing', 'accessory', 'item', 'weapon', etc.

        ❌ DO NOT add to item inventory:
            - Body states or sensations (use memory tool instead)
            - Memories or emotional moments (use memory tool instead)

    Examples:
        # Add
        item(operation="add", item_name="Health Potion", category="consumable")

        # Equip (keeps other slots)
        item(operation="equip", equipment={"top": "White Dress"})

        # Unequip
        item(operation="unequip", slots="weapon")

        # Search
        item(operation="search", category="clothing")

        # History
        item(operation="history", history_slot="weapon", days=30)

        # Memories with item
        item(operation="memories", item_name="白いドレス", top_k=10)
    """
    return await handle_item_operation(
        operation=operation,
        item_name=item_name,
        description=description,
        quantity=quantity,
        category=category,
        tags=tags,
        new_name=new_name,
        equipment=equipment,
        slots=slots,
        auto_add=auto_add,
        query=query,
        history_slot=history_slot,
        days=days,
        mode=mode,
        top_k=top_k
    )
