"""
Search Tools for Memory MCP
Provides keyword search and RAG-based semantic search
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List

# Core imports
from core import (
    get_current_time,
    parse_date_query,
    calculate_time_diff,
)

# Utility imports
from src.utils.persona_utils import get_db_path, get_current_persona

# Qdrant filter imports (Phase 26)
try:
    from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
except ImportError:
    Filter = None
    FieldCondition = None
    MatchValue = None
    Range = None

# Fuzzy matching (optional)
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


async def search_memory(
    query: str = "",
    mode: str = "keyword",
    top_k: int = 5,
    # Keyword mode parameters
    fuzzy_match: bool = False,
    fuzzy_threshold: int = 70,
    tags: Optional[List[str]] = None,
    tag_match_mode: str = "any",
    date_range: Optional[str] = None,
    # Semantic mode parameters
    min_importance: Optional[float] = None,
    emotion: Optional[str] = None,
    action_tag: Optional[str] = None,
    environment: Optional[str] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    relationship_status: Optional[str] = None,
    equipped_item: Optional[str] = None,
    importance_weight: float = 0.0,
    recency_weight: float = 0.0,
    # Related mode parameter
    memory_key: Optional[str] = None
) -> str:
    """
    Unified search interface supporting keyword, semantic (RAG), and related searches.
    
    Args:
        query: Search query or keyword (required for semantic/keyword modes)
        mode: Search mode - "keyword" (default), "semantic", or "related"
        top_k: Max results (default: 5)
        
        # Keyword mode only:
        fuzzy_match: Typo tolerance (default: False)
        fuzzy_threshold: Fuzzy score 0-100 (default: 70)
        tags: Filter by tags (default: None)
        tag_match_mode: "any" (OR) or "all" (AND) (default: "any")
        date_range: Date filter (e.g., "今日", "2025-10-01..2025-10-31")
        
        # Semantic mode only:
        min_importance: Filter by importance 0.0-1.0 (e.g., 0.7 for important only)
        emotion/action_tag/environment/physical_state/mental_state/relationship_status: Context filters
        importance_weight/recency_weight: Custom scoring (0.0-1.0)
        
        # Related mode only:
        memory_key: Memory key to find related memories for (required for mode="related")
        
        # Common filter:
        equipped_item: Filter by equipped item name (partial match)
    
    Examples:
        # Keyword search
        search_memory("Python", mode="keyword")
        search_memory("Pythn", mode="keyword", fuzzy_match=True)
        search_memory("", mode="keyword", tags=["technical_achievement"])
        
        # Semantic search
        search_memory("ユーザーの好きな食べ物", mode="semantic")
        search_memory("成果", mode="semantic", min_importance=0.7)
        
        # Related memories
        search_memory(mode="related", memory_key="memory_20251031123045")
    """
    try:
        if mode == "semantic":
            # Delegate to RAG-based semantic search
            from tools.crud_tools import read_memory
            try:
                return await read_memory(
                    query=query,
                    top_k=top_k,
                    min_importance=min_importance,
                    emotion=emotion,
                    action_tag=action_tag,
                    environment=environment,
                    physical_state=physical_state,
                    mental_state=mental_state,
                    relationship_status=relationship_status,
                    equipped_item=equipped_item,
                    importance_weight=importance_weight,
                    recency_weight=recency_weight
                )
            except Exception as e:
                # Fallback to keyword search if RAG fails
                print(f"⚠️  RAG failed ({e}), falling back to keyword search...")
                return await search_memory(
                    query=query,
                    mode="keyword",
                    top_k=top_k,
                    equipped_item=equipped_item
                )
        
        elif mode == "related":
            # Delegate to similarity-based related search
            from tools.analysis_tools import find_related_memories
            if not memory_key:
                return "❌ mode='related' requires memory_key parameter"
            return await find_related_memories(memory_key, top_k)
        
        elif mode == "keyword":
            # Original keyword search implementation
            persona = get_current_persona()
            current_time = get_current_time()
            db_path = get_db_path()
            
            # Read all memories from database
            memories = {}
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, content, created_at, updated_at, tags, related_keys, equipped_items FROM memories')
                for row in cursor.fetchall():
                    key, content, created_at, updated_at, tags_json, related_keys_json, equipped_items_json = row
                    memories[key] = {
                        "content": content,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "tags": json.loads(tags_json) if tags_json else [],
                        "related_keys": json.loads(related_keys_json) if related_keys_json else [],
                        "equipped_items": json.loads(equipped_items_json) if equipped_items_json else {}
                    }
            
            # Phase 1: Start with all memories as candidates
            candidate_keys = set(memories.keys())
            filter_descriptions = []
            
            # Phase 2: Apply date filter if specified
            if date_range:
                try:
                    start_date, end_date = parse_date_query(date_range)
                    date_filtered = set()
                    for key in candidate_keys:
                        entry = memories[key]
                        created_dt = datetime.fromisoformat(entry['created_at'])
                        # Make timezone-aware if naive
                        if created_dt.tzinfo is None:
                            from src.utils.config_utils import load_config
                            from zoneinfo import ZoneInfo
                            cfg = load_config()
                            tz = ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))
                            created_dt = created_dt.replace(tzinfo=tz)
                        
                        if start_date <= created_dt <= end_date:
                            date_filtered.add(key)
                    
                    candidate_keys = date_filtered
                    filter_descriptions.append(f"date_range={date_range}")
                except (ValueError, TypeError) as e:
                    return f"❌ Invalid date range '{date_range}': {e}"
            
            # Phase 3: Apply tag filter if specified
            if tags:
                tag_filtered = set()
                for key in candidate_keys:
                    entry = memories[key]
                    entry_tags = entry.get('tags', [])
                    
                    if tag_match_mode == "all":
                        # AND mode: entry must have all specified tags
                        if all(tag in entry_tags for tag in tags):
                            tag_filtered.add(key)
                    else:
                        # OR mode (default): entry must have at least one specified tag
                        if any(tag in entry_tags for tag in tags):
                            tag_filtered.add(key)
                
                candidate_keys = tag_filtered
                filter_descriptions.append(f"tags={tags} (mode={tag_match_mode})")
            
            # Phase 4: Apply equipped_item filter if specified
            if equipped_item:
                item_filtered = set()
                for key in candidate_keys:
                    entry = memories[key]
                    equipped_items = entry.get('equipped_items', {})
                    
                    # Search in equipped item values (partial match, case-insensitive)
                    if any(equipped_item.lower() in item.lower() 
                           for item in equipped_items.values() if item):
                        item_filtered.add(key)
                
                candidate_keys = item_filtered
                filter_descriptions.append(f"equipped_item={equipped_item}")
            
            # Phase 5: Keyword matching
            if query:
                keyword_matches = []
                for key in candidate_keys:
                    entry = memories[key]
                    content = entry['content']
                    
                    # Exact or fuzzy match
                    if fuzzy_match and RAPIDFUZZ_AVAILABLE:
                        score = fuzz.partial_ratio(query.lower(), content.lower())
                        if score >= fuzzy_threshold:
                            keyword_matches.append((key, score))
                    else:
                        # Simple substring search (case-insensitive)
                        if query.lower() in content.lower():
                            # Score by position (earlier = higher score)
                            pos = content.lower().index(query.lower())
                            score = 100 - min(pos, 100)
                            keyword_matches.append((key, score))
                
                # Sort by score (descending)
                keyword_matches.sort(key=lambda x: x[1], reverse=True)
                result_keys = [k for k, s in keyword_matches[:top_k]]
            else:
                # No query: return all candidates sorted by recency
                sorted_keys = sorted(candidate_keys, 
                                   key=lambda k: memories[k]['created_at'], 
                                   reverse=True)
                result_keys = sorted_keys[:top_k]
            
            # Phase 6: Format results
            if not result_keys:
                filter_str = f" (filters: {', '.join(filter_descriptions)})" if filter_descriptions else ""
                return f"🔍 No memories found for query '{query}'{filter_str}"
            
            result = f"🔍 Keyword Search Results ({len(result_keys)}/{len(candidate_keys)} memories):\n"
            if filter_descriptions:
                result += f"📌 Filters: {', '.join(filter_descriptions)}\n"
            result += f"🔎 Query: '{query}'\n\n"
            result += f"{'='*50}\n\n"
            
            for idx, key in enumerate(result_keys, 1):
                entry = memories[key]
                content = entry['content']
                created_at = entry['created_at']
                entry_tags = entry.get('tags', [])
                equipped_items = entry.get('equipped_items', {})
                
                # Calculate time difference
                time_diff = calculate_time_diff(created_at)
                
                result += f"{idx}. [{key}]\n"
                result += f"   📅 {time_diff['formatted_string']}前\n"
                result += f"   📝 {content[:150]}{'...' if len(content) > 150 else ''}\n"
                
                if entry_tags:
                    result += f"   🏷️  Tags: {', '.join(entry_tags)}\n"
                
                if equipped_items:
                    equipped_str = ', '.join(f"{slot}:{item}" for slot, item in equipped_items.items() if item)
                    if equipped_str:
                        result += f"   ⚔️  Equipped: {equipped_str}\n"
                
                result += "\n"
            
            result += f"💡 Persona: {persona}"
            return result
        
        else:
            return f"❌ Invalid mode '{mode}'. Use 'keyword', 'semantic', or 'related'."
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Search failed: {str(e)}"


async def search_memory_rag(
    query: str, 
    top_k: int = 5,
    min_importance: Optional[float] = None,
    emotion: Optional[str] = None,
    action_tag: Optional[str] = None,
    environment: Optional[str] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    relationship_status: Optional[str] = None,
    importance_weight: float = 0.0,
    recency_weight: float = 0.0
) -> str:
    """
    DEPRECATED: Use read_memory() instead.
    This function exists for backward compatibility only.
    """
    # Import the new read_memory function
    from tools.crud_tools import read_memory
    
    # Forward all parameters to read_memory
    return await read_memory(
        query=query,
        top_k=top_k,
        min_importance=min_importance,
        emotion=emotion,
        action_tag=action_tag,
        environment=environment,
        physical_state=physical_state,
        mental_state=mental_state,
        relationship_status=relationship_status,
        importance_weight=importance_weight,
        recency_weight=recency_weight
    )
