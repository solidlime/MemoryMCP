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
    Unified memory and context management tool.

    🎯 CRITICAL WORKFLOW:
        1. Session start: ALWAYS call get_context() first
        2. Every turn: Create memory (些細な出来事も含めて毎ターン記憶作成推奨)
        3. Use context_tags for categorization (推奨、必須ではない)

    📋 OPERATIONS:

    Memory CRUD:
        create         - Save new memory with emotion/importance
        read           - Get memory by key or recent entries
        update         - Modify existing memory (including tagged promise/goal status)
        delete         - Remove memory
        search         - Find memories (modes: semantic, keyword, hybrid)
        stats          - Get memory statistics
        check_routines - Find recurring patterns at current time

    Context:
        update_context - Update persona state (emotion, physical, environment)

    Note: Promises/Goals now use tag-based approach (see TAGS section)

    🏷️ TAGS (use with context_tags=[...]):
        - 推奨だが必須ではない（タグなしでも記憶作成OK）
        - 形式: 単語のみ（1-3 words, lowercase, no spaces）
        - 例: ["promise", "milestone", "anniversary", "daily_routine"]

        Special tags:
        anniversary - Commemorative dates (first meeting, milestones)
        promise     - Active promises (track status in persona_info)
        milestone   - Achievements, significant events

    💡 QUICK EXAMPLES:
        # Session start
        get_context()

        # Create memory
        memory(operation="create", content="Learned Python async",
               emotion_type="joy", importance=0.7)

        # Promise (tag-based, recommended)
        memory(operation="create", content="週末にダンス披露",
               context_tags=["promise"],
               persona_info={"status": "active", "priority": 8, "due_date": "2025-02-19"})

        # Complete promise (get key from get_context)
        memory(operation="update", query="memory_20250217_143022",
               persona_info={"status": "completed"})

        # Update state
        memory(operation="update_context",
               physical_state="energetic", mental_state="focused")

    Args:
        operation: Operation type (see OPERATIONS above)
        query: Search query or memory key
        content: Memory content
        context_tags: Tags for categorization (list of strings)
        importance: 0.0-1.0, defaults to 0.5
        persona_info: Dict for status, priority, due_date, etc.
        privacy_level: "public", "internal" (default), "private", "secret"

    Returns:
        Operation result as formatted string
    """
    # Update last conversation time for all operations
    update_last_conversation_time(get_current_persona())

    # Normalize operation - handle common mistakes like "update_context, create_memory_if_not_exists"
    operation = operation.lower().strip()
    if ',' in operation:
        # Take only the first valid operation before comma
        operation = operation.split(',')[0].strip()

    # Remove common suffixes that don't match actual operations
    operation = operation.replace('_if_not_exists', '').replace('_memory', '')

    # Route to appropriate handler
    # Memory operations
    memory_operations = ["create", "read", "update", "delete", "search", "stats", "check_routines"]
    context_operations = ["update_context"]  # promise/goal deprecated - use tag-based memories

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
    Manage persona inventory and equipment.

    🎯 CRITICAL RULES:
        - Physical items ONLY (clothing, accessories, tools)
        - NOT for emotions, body states, or abstract concepts
        - State changes (wet, dirty, etc.) → Use update(), NOT new items

    📋 OPERATIONS:
        add      - Add item to inventory
        remove   - Remove item from inventory
        equip    - Equip items to slots (keeps other equipped items)
        unequip  - Unequip items from slots
        update   - Modify item properties (name, description, state)
        search   - Find items in inventory
        history  - View equipment history
        memories - Get memories associated with item

    ✅ VALID items:
        - Clothing: dresses, shirts, pants, shoes
        - Accessories: jewelry, bags, hats, scarves
        - Tools/Weapons: swords, staffs, potions

    ❌ INVALID items (use memory tool instead):
        - Body states: "疲労", "眠気"
        - Emotions: "喜び", "悲しみ"
        - Abstract concepts: "涙", "汗"
        - Temporary states: "濡れた白いドレス" (→ update existing dress)

    💡 EXAMPLES:
        # Add new item
        item(operation="add", item_name="白いドレス", category="clothing")

        # Equip (keeps other slots)
        item(operation="equip", equipment={"top": "白いドレス", "accessory": "花の髪飾り"})

        # Update item state (NOT new item!)
        item(operation="update", item_name="白いドレス",
             description="雨に濡れた白いドレス（乾燥中）")

        # Search
        item(operation="search", category="clothing")

    Args:
        operation: Operation type (see OPERATIONS above)
        item_name: Item name (most operations)
        equipment: {slot: item_name} dict for equip
        description: Item description (for add/update)
        category: Item category (clothing, accessory, item, weapon)

    Returns:
        Operation result as formatted string
    """
    # Normalize operation - handle common mistakes
    operation = operation.lower().strip()
    if ',' in operation:
        operation = operation.split(',')[0].strip()

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
