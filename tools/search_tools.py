"""
Search Tools for Memory MCP
Provides keyword search and RAG-based semantic search
"""

import re
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple

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


# ============================================================
# Phase 43: Reciprocal Rank Fusion (RRF) for Hybrid Search
# ============================================================

def _extract_memory_keys(result_string: str) -> List[str]:
    """
    Extract memory keys from formatted search result string.

    Args:
        result_string: Formatted search result with [memory_xxx] patterns

    Returns:
        List of memory keys in order of appearance
    """
    pattern = r'\[memory_\d+(?:_[a-zA-Z0-9_]+)?\]'
    matches = re.findall(pattern, result_string)
    # Remove brackets and return unique keys while preserving order
    keys = []
    seen = set()
    for match in matches:
        key = match[1:-1]  # Remove [ and ]
        if key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k: int = 60
) -> List[Tuple[str, float]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion (RRF).

    RRF Formula: score(d) = Σ 1 / (k + rank_i(d))
    where rank_i(d) is the rank of document d in list i.

    Args:
        ranked_lists: List of ranked memory key lists
        k: RRF constant (default: 60, standard value from literature)

    Returns:
        List of (memory_key, rrf_score) tuples sorted by score descending
    """
    rrf_scores = {}

    for ranked_list in ranked_lists:
        for rank, key in enumerate(ranked_list, start=1):
            if key not in rrf_scores:
                rrf_scores[key] = 0.0
            rrf_scores[key] += 1.0 / (k + rank)

    # Sort by score descending
    sorted_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return sorted_results


def _get_memories_by_keys(keys: List[str], persona: str = None) -> Dict[str, dict]:
    """
    Retrieve memory details for given keys.

    Args:
        keys: List of memory keys
        persona: Persona name (default: current)

    Returns:
        Dict mapping keys to memory entries
    """
    if not keys:
        return {}

    if persona is None:
        persona = get_current_persona()

    db_path = get_db_path(persona)
    memories = {}

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(keys))
        query = f"""
            SELECT key, content, created_at, tags, importance,
                   emotion, equipped_items, access_count
            FROM memories
            WHERE key IN ({placeholders})
        """
        cursor.execute(query, keys)

        for row in cursor.fetchall():
            key, content, created_at, tags_json, importance, emotion, equipped_json, access_count = row
            memories[key] = {
                'content': content,
                'created_at': created_at,
                'tags': json.loads(tags_json) if tags_json else [],
                'importance': importance if importance else 0.5,
                'emotion': emotion,
                'equipped_items': json.loads(equipped_json) if equipped_json else {},
                'access_count': access_count if access_count else 0
            }

    return memories


def _format_hybrid_results(
    query: str,
    rrf_results: List[Tuple[str, float]],
    memories: Dict[str, dict],
    persona: str,
    top_k: int = 5
) -> str:
    """
    Format RRF-merged hybrid search results.

    Args:
        query: Search query
        rrf_results: List of (key, rrf_score) tuples
        memories: Dict of memory entries
        persona: Persona name
        top_k: Number of results to display

    Returns:
        Formatted result string
    """
    limited_results = rrf_results[:top_k]

    result = f"🔍 Hybrid Search Results (RRF) for '{query}':\n"
    result += f"📊 Found {len(limited_results)} combined results from semantic + keyword search\n"
    result += "=" * 60 + "\n\n"

    for idx, (key, rrf_score) in enumerate(limited_results, 1):
        if key not in memories:
            continue

        entry = memories[key]
        content = entry['content']
        created_at = entry['created_at']
        tags = entry.get('tags', [])
        importance = entry.get('importance', 0.5)
        equipped_items = entry.get('equipped_items', {})

        time_diff = calculate_time_diff(created_at)

        result += f"{idx}. [{key}] (RRF score: {rrf_score:.4f})\n"
        result += f"   📅 {time_diff['formatted_string']}前\n"
        result += f"   ⭐ 重要度: {importance:.2f}\n"
        result += f"   📝 {content}\n"

        if tags:
            result += f"   🏷️  Tags: {', '.join(tags)}\n"

        if equipped_items:
            equipped_str = ', '.join(f"{slot}:{item}" for slot, item in equipped_items.items() if item)
            if equipped_str:
                result += f"   ⚔️  Equipped: {equipped_str}\n"

        result += "\n"

    result += f"💡 Persona: {persona}\n"
    result += f"ℹ️  RRF combines semantic (meaning-based) and keyword (exact-match) results"

    return result


async def search_memory(
    query: str = "",
    mode: str = "hybrid",  # Changed default to hybrid
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
        mode: Search mode - "hybrid" (default), "keyword", "semantic", "related", "task", or "plan"
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
        # Hybrid search (Recommended)
        search_memory("Python project")

        # Keyword search (default: OR)
        search_memory("Python Rust", mode="keyword")  # Matches Python OR Rust
        search_memory("Python AND Rust", mode="keyword")  # Matches Python AND Rust

        # Semantic search (RAG only)
        search_memory("ユーザーの好きな食べ物", mode="semantic")

        # Related memories
        search_memory(mode="related", memory_key="memory_20251031123045")

        # Task/Plan search (未完了のタスクや予定を検索)
        search_memory(mode="task")  # All tasks
        search_memory(mode="plan")  # All plans
        search_memory("dashboard", mode="task")  # Search tasks containing "dashboard"
    """
    from core import update_last_conversation_time

    try:
        # Update last conversation time
        persona = get_current_persona()
        update_last_conversation_time(persona)

        if mode == "task" or mode == "plan":
            # Task/Plan専用検索
            persona = get_current_persona()
            db_path = get_db_path()

            # Task/Planに関連するタグ
            task_tags = ["plan", "TODO", "todo", "task", "タスク", "予定", "実装予定", "milestone"]
            plan_tags = ["plan", "予定", "計画", "future", "upcoming"]

            target_tags = task_tags if mode == "task" else plan_tags

            memories = {}
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, content, created_at, updated_at, tags, importance FROM memories ORDER BY created_at DESC')
                for row in cursor.fetchall():
                    key, content, created_at, updated_at, tags_json, imp = row
                    tags_list = json.loads(tags_json) if tags_json else []

                    # Check if any tag matches
                    has_tag = any(tag in tags_list for tag in target_tags)

                    # Also check content for keywords
                    content_lower = content.lower()
                    has_keyword = any(keyword in content_lower for keyword in [
                        "実装", "予定", "タスク", "todo", "plan", "優先度", "milestone",
                        "やりたい", "実装する", "追加する", "改善", "機能"
                    ])

                    if has_tag or has_keyword:
                        memories[key] = {
                            "content": content,
                            "created_at": created_at,
                            "updated_at": updated_at,
                            "tags": tags_list,
                            "importance": imp if imp else 0.5
                        }

            if query:
                # Filter by query
                filtered = {}
                for key, entry in memories.items():
                    if query.lower() in entry['content'].lower():
                        filtered[key] = entry
                memories = filtered

            if not memories:
                mode_jp = "タスク" if mode == "task" else "予定・計画"
                query_str = f" containing '{query}'" if query else ""
                return f"📋 No {mode_jp} found{query_str}"

            # Sort by importance and recency
            sorted_keys = sorted(
                memories.keys(),
                key=lambda k: (memories[k].get('importance', 0.5), memories[k]['created_at']),
                reverse=True
            )[:top_k]

            mode_icon = "📋" if mode == "task" else "📅"
            mode_jp = "タスク" if mode == "task" else "予定・計画"
            result = f"{mode_icon} {mode_jp} Search Results ({len(sorted_keys)} found):\n"
            if query:
                result += f"🔎 Query: '{query}'\n"
            result += "=" * 60 + "\n\n"

            for idx, key in enumerate(sorted_keys, 1):
                entry = memories[key]
                content = entry['content']
                created_at = entry['created_at']
                importance = entry.get('importance', 0.5)
                tags_list = entry.get('tags', [])

                time_diff = calculate_time_diff(created_at)

                result += f"{idx}. [{key}]\n"
                result += f"   📅 {time_diff['formatted_string']}前\n"
                result += f"   ⭐ 重要度: {importance:.2f}\n"
                result += f"   📝 {content}\n"

                if tags_list:
                    result += f"   🏷️  Tags: {', '.join(tags_list)}\n"

                result += "\n"

            result += f"💡 Persona: {persona}"
            return result

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

        elif mode == "hybrid" or mode == "integrated":
            # Phase 43: Hybrid Search with Reciprocal Rank Fusion (RRF)
            ranked_lists = []

            # 1. Run Semantic Search (RAG)
            semantic_keys = []
            try:
                from tools.crud_tools import read_memory
                semantic_result = await read_memory(
                    query=query,
                    top_k=top_k * 2,  # Get more candidates for RRF
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
                semantic_keys = _extract_memory_keys(semantic_result)
                if semantic_keys:
                    ranked_lists.append(semantic_keys)
            except Exception as e:
                from src.utils.logging_utils import log_progress
                log_progress(f"⚠️ Semantic search failed in hybrid mode: {e}")

            # 2. Run Keyword Search (if query provided)
            keyword_keys = []
            if query:
                try:
                    keyword_result = await search_memory(
                        query=query,
                        mode="keyword",
                        top_k=top_k * 2,  # Get more candidates for RRF
                        fuzzy_match=fuzzy_match,
                        fuzzy_threshold=fuzzy_threshold,
                        tags=tags,
                        tag_match_mode=tag_match_mode,
                        date_range=date_range,
                        equipped_item=equipped_item
                    )
                    keyword_keys = _extract_memory_keys(keyword_result)
                    if keyword_keys:
                        ranked_lists.append(keyword_keys)
                except Exception as e:
                    from src.utils.logging_utils import log_progress
                    log_progress(f"⚠️ Keyword search failed in hybrid mode: {e}")

            # 3. Apply Reciprocal Rank Fusion
            if not ranked_lists:
                return f"📭 No memories found for '{query}' (checked both semantic and keyword)."

            rrf_results = _reciprocal_rank_fusion(ranked_lists, k=60)

            # 4. Retrieve memory details
            result_keys = [key for key, score in rrf_results[:top_k * 2]]
            memories = _get_memories_by_keys(result_keys, persona)

            # 5. Format and return results
            return _format_hybrid_results(
                query=query,
                rrf_results=rrf_results,
                memories=memories,
                persona=persona,
                top_k=top_k
            )

        elif mode == "progressive":
            # Progressive Disclosure Search (claude-mem inspired)
            # Stage 1: Fast keyword/tag search (SQLite only, no ML)
            # Stage 2: Only if keyword results < threshold, escalate to semantic
            # This is DS920+ friendly - avoids heavy ML unless needed
            from src.utils.config_utils import load_config
            cfg = load_config()
            prog_cfg = cfg.get("progressive_search", {})
            threshold = prog_cfg.get("keyword_threshold", 3)
            semantic_fallback = prog_cfg.get("semantic_fallback", True)
            max_semantic = prog_cfg.get("max_semantic_top_k", 5)

            # Stage 1: Keyword search (fast, SQLite)
            keyword_result = await search_memory(
                query=query,
                mode="keyword",
                top_k=top_k,
                fuzzy_match=fuzzy_match,
                fuzzy_threshold=fuzzy_threshold,
                tags=tags,
                tag_match_mode=tag_match_mode,
                date_range=date_range,
                equipped_item=equipped_item
            )

            # Count keyword hits
            keyword_hits = keyword_result.count("[memory_") if "Found" in keyword_result or "memories)" in keyword_result else 0

            result = f"🔍 Progressive Search for '{query}':\n\n"

            if keyword_hits >= threshold:
                # Enough keyword results - skip semantic
                result += f"📝 Stage 1 (Keyword): {keyword_hits} matches found ✓\n"
                result += "⚡ Skipped semantic search (sufficient keyword matches)\n\n"
                result += keyword_result
                return result

            # Stage 2: Semantic fallback (heavier, ML-based)
            result += f"📝 Stage 1 (Keyword): {keyword_hits} match(es)\n"

            if semantic_fallback and query:
                result += "🧠 Stage 2 (Semantic): Escalating...\n\n"
                try:
                    from tools.crud_tools import read_memory
                    semantic_result = await read_memory(
                        query=query,
                        top_k=min(top_k, max_semantic),
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

                    if keyword_hits > 0:
                        result += "--- Keyword Results ---\n"
                        result += keyword_result + "\n\n"

                    result += "--- Semantic Results ---\n"
                    result += semantic_result
                except Exception as e:
                    result += f"⚠️ Semantic search failed: {e}\n"
                    if keyword_hits > 0:
                        result += keyword_result
                    else:
                        result += "📭 No results found."
            else:
                if keyword_hits > 0:
                    result += keyword_result
                else:
                    result += "📭 No results found."

            return result

        elif mode == "keyword":
            # Original keyword search implementation
            persona = get_current_persona()
            current_time = get_current_time()
            db_path = get_db_path()

            # Read all memories from database
            memories = {}
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, content, created_at, updated_at, tags, related_keys, equipped_items, privacy_level FROM memories')
                for row in cursor.fetchall():
                    key, content, created_at, updated_at, tags_json, related_keys_json, equipped_items_json, priv_level = row
                    memories[key] = {
                        "content": content,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "tags": json.loads(tags_json) if tags_json else [],
                        "related_keys": json.loads(related_keys_json) if related_keys_json else [],
                        "equipped_items": json.loads(equipped_items_json) if equipped_items_json else {},
                        "privacy_level": priv_level if priv_level else "internal"
                    }

            # Privacy filter: exclude secret memories from search
            from src.utils.config_utils import load_config as _load_cfg
            _privacy_cfg = _load_cfg().get("privacy", {})
            _search_max = _privacy_cfg.get("search_max_level", "private")
            _PRIV_RANK = {"public": 0, "internal": 1, "private": 2, "secret": 3}
            _max_rank = _PRIV_RANK.get(_search_max, 2)
            memories = {k: v for k, v in memories.items()
                       if _PRIV_RANK.get(v.get("privacy_level", "internal"), 1) <= _max_rank}

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

            # Phase 5: Keyword matching with Boolean support
            if query:
                keyword_matches = []

                # Parse query for Boolean logic
                # Default: "A B" -> match A or B (implicit OR)
                # Explicit: "A AND B" -> match A and B

                # Split by AND first
                and_groups = [g.strip() for g in query.split(" AND ")]

                for key in candidate_keys:
                    entry = memories[key]
                    content = entry['content']
                    content_lower = content.lower()

                    is_match = True
                    match_score = 0

                    # All AND groups must match
                    for and_group in and_groups:
                        # Within each AND group, terms are OR'ed (space separated)
                        or_terms = [t.strip() for t in and_group.split() if t.strip()]
                        if not or_terms:
                            continue

                        # At least one OR term must be present
                        group_matched = any(term.lower() in content_lower for term in or_terms)
                        
                        if not group_matched:
                            is_match = False
                            break
                        
                        # Score based on first matching term position
                        for term in or_terms:
                            if term.lower() in content_lower:
                                pos = content_lower.find(term.lower())
                                match_score = max(match_score, 100 - min(pos, 100))
                                break

                    if is_match:
                        keyword_matches.append((key, match_score))

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
                result += f"   📝 {content}\n"

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
            return f"❌ Invalid mode '{mode}'. Use 'hybrid', 'keyword', 'semantic', 'related', or 'progressive'."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Search failed: {str(e)}"
