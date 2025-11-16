"""
Unified Tool Interface for Memory-MCP
Consolidates multiple operations into single tools with operation parameter.

This reduces context consumption by minimizing the number of exposed tools.
"""

from typing import Optional, List, Dict

# Import existing CRUD operations
from tools.crud_tools import (
    create_memory as _create_memory,
    read_memory as _read_memory,
    update_memory as _update_memory,
    delete_memory as _delete_memory,
    get_memory_stats as _get_memory_stats
)

# Import search operations
from tools.search_tools import search_memory as _search_memory

# Import equipment operations
from tools.equipment_tools import (
    add_to_inventory as _add_to_inventory,
    remove_from_inventory as _remove_from_inventory,
    equip_item as _equip_item,
    update_item as _update_item,
    search_inventory as _search_inventory,
    get_equipment_history as _get_equipment_history
)

# Import item-memory analysis
from tools.item_memory_tools import (
    get_memories_with_item as _get_memories_with_item,
    get_item_usage_stats as _get_item_usage_stats
)


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
    # Search-specific parameters
    mode: str = "keyword",
    fuzzy_match: bool = False,
    fuzzy_threshold: int = 70,
    tags: Optional[List[str]] = None,
    tag_match_mode: str = "any",
    date_range: Optional[str] = None,
    min_importance: Optional[float] = None,
    equipped_item: Optional[str] = None,
    importance_weight: float = 0.0,
    recency_weight: float = 0.0,
    memory_key: Optional[str] = None
) -> str:
    """
    Unified memory operations interface.
    
    Args:
        operation: Operation type - "create", "read", "update", "delete", "search", "stats"
        query: Search query or natural language for update/delete
        content: Memory content (required for create/update)
        
    Operations:
        - "create": Create new memory (requires content)
        - "read": Semantic search with RAG (requires query)
        - "update": Update memory by query (requires query, content)
        - "delete": Delete memory by key or query (requires query)
        - "search": Keyword/semantic/related search (requires query or memory_key for related mode)
        - "stats": Get memory statistics
    
    **Recommended Tags** (Use English consistently):
        - Technical: "technical_achievement", "bug_fix", "code_refactor", "learning"
        - Emotional: "emotional_moment", "intimate_moment", "happy_moment", "sad_moment"
        - Events: "important_event", "promise", "plan", "milestone"
        - Relationship: "relationship_update", "conversation", "disagreement"
        - Daily: "daily_activity", "routine", "meal", "rest"
    
    Examples:
        # Create with recommended tags
        memory(operation="create", content="User completed Python project", 
               emotion_type="joy", importance=0.8, 
               context_tags=["technical_achievement", "milestone"])
        
        # Create with all available fields
        memory(operation="create", 
               content="Walked together in the park at sunset",
               emotion_type="joy", emotion_intensity=0.85,
               physical_state="energized", mental_state="peaceful",
               environment="park", relationship_status="married",
               action_tag="walking", importance=0.7,
               context_tags=["emotional_moment", "daily_activity"],
               persona_info={"favorite_items": ["sunset", "nature"]},
               user_info={"name": "User"})
        
        # Read (semantic search)
        memory(operation="read", query="ユーザーの好きな食べ物", top_k=5)
        
        # Update
        memory(operation="update", query="promise", content="Changed to tomorrow 10am")
        
        # Delete
        memory(operation="delete", query="memory_20251102083918")
        
        # Search (keyword)
        memory(operation="search", query="Python", mode="keyword", tags=["technical_achievement"])
        
        # Search (semantic)
        memory(operation="search", query="成果", mode="semantic", min_importance=0.7)
        
        # Search (related)
        memory(operation="search", mode="related", memory_key="memory_20251031123045")
        
        # Stats
        memory(operation="stats")
    """
    operation = operation.lower()
    
    if operation == "create":
        if not content:
            return "❌ Error: 'content' is required for create operation"
        return await _create_memory(
            content=content,
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
            action_tag=action_tag
        )
    
    elif operation == "read":
        if not query:
            return "❌ Error: 'query' is required for read operation"
        return await _read_memory(
            query=query,
            top_k=top_k,
            min_importance=min_importance,
            emotion=emotion_type,
            action_tag=action_tag,
            environment=environment,
            physical_state=physical_state,
            mental_state=mental_state,
            relationship_status=relationship_status,
            equipped_item=equipped_item,
            importance_weight=importance_weight,
            recency_weight=recency_weight
        )
    
    elif operation == "update":
        if not query:
            return "❌ Error: 'query' is required for update operation"
        if not content:
            return "❌ Error: 'content' is required for update operation"
        return await _update_memory(
            query=query,
            content=content,
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
            action_tag=action_tag
        )
    
    elif operation == "delete":
        if not query:
            return "❌ Error: 'query' (key or natural language) is required for delete operation"
        return await _delete_memory(query)
    
    elif operation == "search":
        return await _search_memory(
            query=query or "",
            mode=mode,
            top_k=top_k,
            fuzzy_match=fuzzy_match,
            fuzzy_threshold=fuzzy_threshold,
            tags=tags,
            tag_match_mode=tag_match_mode,
            date_range=date_range,
            min_importance=min_importance,
            emotion=emotion_type,
            action_tag=action_tag,
            environment=environment,
            physical_state=physical_state,
            mental_state=mental_state,
            relationship_status=relationship_status,
            equipped_item=equipped_item,
            importance_weight=importance_weight,
            recency_weight=recency_weight,
            memory_key=memory_key
        )
    
    elif operation == "stats":
        return await _get_memory_stats()
    
    else:
        return f"❌ Error: Unknown operation '{operation}'. Valid: create, read, update, delete, search, stats"


async def item(
    operation: str,
    # Common parameters
    item_name: Optional[str] = None,
    # Add/Update parameters
    description: Optional[str] = None,
    quantity: int = 1,
    category: Optional[str] = None,
    tags: Optional[list] = None,
    # Equip parameters
    equipment: Optional[Dict[str, str]] = None,
    # Search parameters
    query: Optional[str] = None,
    # History parameters
    slot: Optional[str] = None,
    days: int = 7,
    # Analysis parameters
    mode: str = "memories",
    top_k: int = 10
) -> str:
    """
    Unified item operations interface.
    
    Args:
        operation: Operation type - "add", "remove", "equip", "update", "search", "history", "memories", "stats"
        item_name: Item name (required for most operations)
        
    Operations:
        - "add": Add item to inventory
        - "remove": Remove item from inventory
        - "equip": Equip items (batch mode, unequips all first)
        - "update": Update item metadata
        - "search": Search inventory
        - "history": Get equipment change history
        - "memories": Find memories containing item
        - "stats": Get item usage statistics
    
    Examples:
        # Add
        item(operation="add", item_name="Health Potion", description="Restores HP", 
             quantity=5, category="consumable")
        
        # Remove
        item(operation="remove", item_name="Health Potion", quantity=2)
        
        # Equip (batch)
        item(operation="equip", equipment={"weapon": "Steel Sword", "armor": "Leather Armor"})
        
        # Update
        item(operation="update", item_name="Steel Sword", description="Very sharp blade")
        
        # Search (all items)
        item(operation="search")
        
        # Search (filtered)
        item(operation="search", category="weapon")
        item(operation="search", query="sword")
        
        # History
        item(operation="history", slot="weapon", days=30)
        
        # Memories with item
        item(operation="memories", item_name="白いドレス", top_k=10)
        
        # Usage stats
        item(operation="stats", item_name="Steel Sword")
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
    
    elif operation == "update":
        if not item_name:
            return "❌ Error: 'item_name' is required for update operation"
        return _update_item(
            item_name=item_name,
            description=description,
            category=category,
            tags=tags
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
            slot=slot,
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
        return f"❌ Error: Unknown operation '{operation}'. Valid: add, remove, equip, update, search, history, memories, stats"
