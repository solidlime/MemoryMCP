"""Memory operation handlers for unified memory tool."""

from typing import Optional, List, Dict

# Import existing CRUD operations
from tools.crud_tools import (
    create_memory as _create_memory,
    read_memory as _read_memory,
    update_memory as _update_memory,
    delete_memory as _delete_memory,
    get_memory_stats as _get_memory_stats,
    db_get_entry,
    db_recent_keys,
)

# Import search operations
from tools.search_tools import search_memory as _search_memory

# Import helpers
from tools.helpers.query_helpers import build_expanded_query
from tools.helpers.routine_helpers import check_routines


async def handle_create(
    content: str,
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
    privacy_level: Optional[str] = None,
    defer_vector: bool = False
) -> str:
    """Handle memory creation."""
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
        action_tag=action_tag,
        privacy_level=privacy_level,
        defer_vector=defer_vector
    )


async def handle_read(query: Optional[str], top_k: int) -> str:
    """Handle memory reading."""
    if query and query.startswith("memory_"):
        # Direct key read
        entry = db_get_entry(query)
        if entry:
            result = f"📖 Memory {query}:\n"
            result += f"   {entry['content']}\n"
            result += f"   (Created: {entry['created_at']}, Tags: {entry.get('tags', [])})"
            return result
        else:
            return f"❌ Memory {query} not found."
    elif query:
        return "❌ For search queries, please use operation='search'. 'read' is for reading specific memories by key (query='memory_...') or recent memories (query=None)."

    # Return recent memories
    recent_keys = db_recent_keys(limit=top_k)
    if not recent_keys:
        return "📭 No memories found."

    result = f"🕐 Recent {len(recent_keys)} Memories:\n"
    for i, key in enumerate(recent_keys, 1):
        entry = db_get_entry(key)
        if entry:
            preview = entry['content'][:100] + "..." if len(entry['content']) > 100 else entry['content']
            result += f"{i}. [{key}] {preview}\n"
    return result


async def handle_update(
    query: str,
    content: str,
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
    action_tag: Optional[str] = None
) -> str:
    """Handle memory update."""
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


async def handle_delete(query: str) -> str:
    """Handle memory deletion."""
    return await _delete_memory(query)


async def handle_search(
    query: Optional[str],
    mode: str,
    top_k: int,
    fuzzy_match: bool,
    fuzzy_threshold: int,
    search_tags: Optional[List[str]],
    tag_match_mode: str,
    date_range: Optional[str],
    min_importance: Optional[float],
    emotion_type: Optional[str],
    action_tag: Optional[str],
    environment: Optional[str],
    physical_state: Optional[str],
    mental_state: Optional[str],
    relationship_status: Optional[str],
    equipped_item: Optional[str],
    importance_weight: float,
    recency_weight: float,
    memory_key: Optional[str]
) -> str:
    """Handle memory search."""
    # Smart mode: auto-expand context for ambiguous queries
    if mode == "smart":
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config

        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo")))

        # Build expanded query
        expanded_query, updated_tags = build_expanded_query(query, now, search_tags)

        # Search with hybrid mode
        return await _search_memory(
            query=expanded_query,
            mode="hybrid",
            top_k=top_k,
            fuzzy_match=fuzzy_match,
            fuzzy_threshold=fuzzy_threshold,
            tags=updated_tags,
            tag_match_mode=tag_match_mode,
            date_range=date_range or "last_30_days",
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
    else:
        return await _search_memory(
            query=query or "",
            mode=mode,
            top_k=top_k,
            fuzzy_match=fuzzy_match,
            fuzzy_threshold=fuzzy_threshold,
            tags=search_tags,
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


async def handle_stats() -> str:
    """Handle memory stats retrieval."""
    return await _get_memory_stats()


def handle_check_routines(
    mode: str,
    query: Optional[str],
    top_k: int
) -> str:
    """Handle routine checking."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.utils.config_utils import load_config
    from src.utils.persona_utils import get_current_persona, get_db_path

    persona = get_current_persona()
    cfg = load_config()
    now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo")))
    current_hour = now.hour
    current_weekday = now.strftime("%A")
    db_path = get_db_path()

    # Check if detailed mode requested
    detailed = mode == "detailed" or query == "all" or query == "detailed"

    return check_routines(persona, current_hour, current_weekday, db_path, top_k, detailed)


async def handle_memory_operation(
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
    Handle memory operations.

    Args:
        operation: Operation type (create, read, update, delete, search, stats, check_routines)
        query: Search query or memory key
        content: Memory content
        ... (other parameters as documented in unified_tools.memory)

    Returns:
        Operation result string
    """
    operation = operation.lower()

    if operation == "create":
        if not content:
            return "❌ Error: 'content' is required for create operation"
        return await handle_create(
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
            action_tag=action_tag,
            privacy_level=privacy_level,
            defer_vector=defer_vector
        )

    elif operation == "read":
        return await handle_read(query, top_k)

    elif operation == "update":
        if not query:
            return "❌ Error: 'query' is required for update operation"
        if not content:
            return "❌ Error: 'content' is required for update operation"
        return await handle_update(
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
        return await handle_delete(query)

    elif operation == "search":
        return await handle_search(
            query=query,
            mode=mode,
            top_k=top_k,
            fuzzy_match=fuzzy_match,
            fuzzy_threshold=fuzzy_threshold,
            search_tags=search_tags,
            tag_match_mode=tag_match_mode,
            date_range=date_range,
            min_importance=min_importance,
            emotion_type=emotion_type,
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
        return await handle_stats()

    elif operation == "check_routines":
        return handle_check_routines(mode, query, top_k)

    else:
        return f"❌ Error: Unknown operation '{operation}'. Valid: create, read, update, delete, search, stats, check_routines"
