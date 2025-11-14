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
    top_k: int = 5,
    fuzzy_match: bool = False,
    fuzzy_threshold: int = 70,
    tags: Optional[List[str]] = None,
    tag_match_mode: str = "any",
    date_range: Optional[str] = None,
    equipped_item: Optional[str] = None
) -> str:
    """
    Keyword, tag, and date-based search with optional fuzzy matching.
    
    Args:
        query: Keyword (default: "" = all)
        top_k: Max results (default: 5)
        fuzzy_match: Typo tolerance (default: False)
        fuzzy_threshold: Fuzzy score 0-100 (default: 70)
        tags: Filter by tags (default: None)
        tag_match_mode: "any" (OR) or "all" (AND) (default: "any")
        date_range: Date filter (e.g., "今日", "2025-10-01..2025-10-31")
        equipped_item: Filter by equipped item name (partial match)
    
    Examples:
        search_memory("Python")
        search_memory("Pythn", fuzzy_match=True)
        search_memory("", tags=["technical_achievement"])
        search_memory("Phase", tags=["important_event"], date_range="今月")
        search_memory("", equipped_item="白いドレス")
    """
    try:
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
                        created_dt = created_dt.replace(tzinfo=start_date.tzinfo)
                    if start_date <= created_dt <= end_date:
                        date_filtered.add(key)
                candidate_keys &= date_filtered
                filter_descriptions.append(f"📅 {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            except ValueError as e:
                return str(e)
        
        # Phase 3: Apply tag filter if specified
        if tags:
            tag_filtered = set()
            for key in candidate_keys:
                entry = memories[key]
                entry_tags = entry.get('tags', [])
                
                if tag_match_mode == "all":
                    # AND logic: all tags must be present
                    if entry_tags and all(tag in entry_tags for tag in tags):
                        tag_filtered.add(key)
                else:
                    # OR logic: any tag must be present (default)
                    if entry_tags and any(tag in entry_tags for tag in tags):
                        tag_filtered.add(key)
            
            candidate_keys &= tag_filtered
            logic_str = "ALL" if tag_match_mode == "all" else "ANY"
            filter_descriptions.append(f"🏷️  {logic_str} of {tags}")
        
        # Phase 3.5: Apply equipped item filter if specified
        if equipped_item:
            equipment_filtered = set()
            for key in candidate_keys:
                entry = memories[key]
                equipped_items = entry.get('equipped_items', {})
                # Check if any equipped item contains the search term (partial match)
                if any(equipped_item.lower() in item_name.lower() for item_name in equipped_items.values() if item_name):
                    equipment_filtered.add(key)
            
            candidate_keys &= equipment_filtered
            filter_descriptions.append(f"👗 Equipped: '{equipped_item}'")
        
        # Phase 4: Apply keyword/fuzzy search (if query provided)
        scored_results = []
        
        if not query:
            # No query: return all candidates (filtered by date/tags only)
            for key in candidate_keys:
                entry = memories[key]
                created_dt = datetime.fromisoformat(entry['created_at'])
                scored_results.append((key, entry, created_dt, 100))  # Score 100 for all
        elif fuzzy_match and RAPIDFUZZ_AVAILABLE:
            # Fuzzy matching mode
            for key in candidate_keys:
                entry = memories[key]
                content = entry['content']
                # Use partial_ratio + word-by-word matching
                partial_score = fuzz.partial_ratio(query.lower(), content.lower())
                words = content.split()
                word_scores = [fuzz.ratio(query.lower(), word.lower()) for word in words if len(word) >= 2]
                best_word_score = max(word_scores) if word_scores else 0
                score = max(partial_score, best_word_score)
                
                if score >= fuzzy_threshold:
                    created_dt = datetime.fromisoformat(entry['created_at'])
                    scored_results.append((key, entry, created_dt, score))
            
            filter_descriptions.append(f"🔍 Fuzzy: '{query}' (≥{fuzzy_threshold}%)")
        else:
            # Exact keyword matching mode
            if fuzzy_match and not RAPIDFUZZ_AVAILABLE:
                print("⚠️  Fuzzy matching requested but rapidfuzz not available, using exact match...")
            
            for key in candidate_keys:
                entry = memories[key]
                if query.lower() in entry['content'].lower():
                    created_dt = datetime.fromisoformat(entry['created_at'])
                    scored_results.append((key, entry, created_dt, 100))  # Score 100 for exact match
            
            filter_descriptions.append(f"🔍 Keyword: '{query}'")
        
        # Phase 5: Sort and format results
        # Sort by score (desc), then by date (desc)
        scored_results.sort(key=lambda x: (x[3], x[2]), reverse=True)
        scored_results = scored_results[:top_k]
        
        if scored_results:
            filter_str = " + ".join(filter_descriptions) if filter_descriptions else "No filters"
            result = f"Found {len(scored_results)} memories ({filter_str}, persona: {persona}):\n\n"
            
            for i, (key, entry, created_dt, score) in enumerate(scored_results, 1):
                created_date = entry['created_at'][:10]
                created_time = entry['created_at'][11:19]
                content = entry['content']
                
                # Calculate time elapsed
                time_diff = calculate_time_diff(entry['created_at'])
                time_ago = f" ({time_diff['formatted_string']}前)"
                
                # Get tags
                entry_tags = entry.get('tags', [])
                tags_str = f" [{', '.join(entry_tags)}]" if entry_tags else ""
                
                # Get related keys
                related_keys = entry.get('related_keys', [])
                related_str = f" 🔗{len(related_keys)}関連" if related_keys else ""
                
                # Show score if fuzzy or multiple results
                score_str = f" (Match: {score:.0f}%)" if fuzzy_match or len(scored_results) > 1 else ""
                
                result += f"{i}. [{key}]{tags_str}{related_str}{score_str}\n"
                
                # Show snippet with keyword highlighting
                if query.lower() in content.lower():
                    start = content.lower().find(query.lower())
                    snippet_start = max(0, start - 50)
                    snippet_end = min(len(content), start + len(query) + 50)
                    snippet = content[snippet_start:snippet_end]
                    if snippet_start > 0:
                        snippet = "..." + snippet
                    if snippet_end < len(content):
                        snippet = snippet + "..."
                    result += f"   \"{snippet}\"\n"
                else:
                    result += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n"
                
                result += f"   {created_date} {created_time}{time_ago}\n"
                
                # Show related memories with content preview
                if related_keys:
                    result += f"   🔗 関連記憶:\n"
                    for rel_key in related_keys[:3]:  # Show max 3
                        if rel_key in memories:
                            rel_content = memories[rel_key]['content'][:60]
                            result += f"      • [{rel_key}] {rel_content}...\n"
                    if len(related_keys) > 3:
                        result += f"      (+{len(related_keys) - 3}件の関連記憶)\n"
                
                result += "\n"
            
            return result.rstrip()
        else:
            filter_str = " + ".join(filter_descriptions) if filter_descriptions else "No filters applied"
            return f"No memories found ({filter_str}, persona: {persona})."
    except Exception as e:
        return f"Failed to search memories: {str(e)}"


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
