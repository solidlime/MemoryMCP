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
from persona_utils import get_db_path, get_current_persona

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
    date_range: Optional[str] = None
) -> str:
    """
    Universal search tool for structured queries (keywords, dates, tags).
    For natural language queries, use search_memory_rag instead.
    
    Args:
        query: Keyword to search for in memory contents (default: "" - all memories)
        top_k: Maximum number of results to return (default: 5)
        fuzzy_match: Enable fuzzy matching for typos and variations (default: False)
        fuzzy_threshold: Minimum similarity score (0-100) for fuzzy matches (default: 70)
        tags: Optional list of tags to filter by (default: None)
        tag_match_mode: "any" (OR) or "all" (AND) for tag matching (default: "any")
        date_range: Optional date filter (e.g., "今日", "昨日", "2025-10-01..2025-10-31") (default: None)
    
    Examples:
        - search_memory("Python") → Simple keyword search
        - search_memory("Pythn", fuzzy_match=True) → Fuzzy search with typo tolerance
        - search_memory("", tags=["technical_achievement"]) → Tag-only filter
        - search_memory("Phase", tags=["technical_achievement"]) → Keyword + tag filter
        - search_memory("Phase", date_range="今月") → Keyword + date filter
        - search_memory("Phase", tags=["important_event", "technical_achievement"], tag_match_mode="all", date_range="今月")
          → Full combination: keyword + tags (AND) + date range
    """
    try:
        persona = get_current_persona()
        current_time = get_current_time()
        db_path = get_db_path()
        
        # Read all memories from database
        memories = {}
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, content, created_at, updated_at, tags FROM memories')
            for row in cursor.fetchall():
                key, content, created_at, updated_at, tags_json = row
                memories[key] = {
                    "content": content,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "tags": json.loads(tags_json) if tags_json else []
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
                
                # Show score if fuzzy or multiple results
                score_str = f" (Match: {score:.0f}%)" if fuzzy_match or len(scored_results) > 1 else ""
                
                result += f"{i}. [{key}]{tags_str}{score_str}\n"
                
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
                
                result += f"   {created_date} {created_time}{time_ago}\n\n"
            
            return result.rstrip()
        else:
            filter_str = " + ".join(filter_descriptions) if filter_descriptions else "No filters applied"
            return f"No memories found ({filter_str}, persona: {persona})."
    except Exception as e:
        return f"Failed to search memories: {str(e)}"


async def search_memory_rag(
    query: str, 
    top_k: int = 5,
    # 🆕 Phase 26: フィルタリングパラメータ
    min_importance: Optional[float] = None,
    emotion: Optional[str] = None,
    action_tag: Optional[str] = None,
    environment: Optional[str] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    relationship_status: Optional[str] = None,
    # 🆕 Phase 26: スコアリング調整
    importance_weight: float = 0.0,
    recency_weight: float = 0.0
) -> str:
    """
    Search memories using RAG (Retrieval-Augmented Generation) with embedding-based similarity search.
    More intelligent than keyword search - understands meaning and context.
    
    🆕 Phase 26: Enhanced with metadata filtering and custom scoring!
    
    Args:
        query: Natural language query to search for
        top_k: Number of top results to return (default: 5, recommended: 3-10)
        
        # Filtering (all optional)
        min_importance: Minimum importance score (0.0-1.0, e.g., 0.7 for important memories only)
        emotion: Filter by emotion (e.g., "joy", "love", "neutral")
        action_tag: Filter by activity (e.g., "coding", "kissing", "cooking")
        environment: Filter by location (e.g., "home", "office")
        physical_state: Filter by physical condition (e.g., "energetic", "tired")
        mental_state: Filter by mental state (e.g., "focused", "calm")
        relationship_status: Filter by relationship (e.g., "closer", "intimate")
        
        # Scoring (Phase 26.2)
        importance_weight: Weight for importance score (0.0-1.0, default: 0.0)
        recency_weight: Weight for recency (newer = higher, 0.0-1.0, default: 0.0)
    
    Examples:
        # Basic usage (unchanged)
        - search_memory_rag("Python関連の成果")
        
        # 🆕 Filter by importance
        - search_memory_rag("最近の成果", min_importance=0.7)
        
        # 🆕 Filter by emotion + action
        - search_memory_rag("幸せな時間", emotion="joy", action_tag="kissing")
        
        # 🆕 Multiple filters
        - search_memory_rag("開発作業", min_importance=0.6, action_tag="coding", environment="home")
        
        # 🆕 Custom scoring (Phase 26.2)
        - search_memory_rag("成果", importance_weight=0.3, recency_weight=0.1)
    """
    try:
        persona = get_current_persona()
        
        if not query:
            return "Please provide a query to search."
        
        # Check if RAG system is ready, fallback to keyword search if not
        from vector_utils import embeddings, reranker
        from lib.backends.qdrant_backend import QdrantVectorStoreAdapter
        from config_utils import load_config
        from qdrant_client import QdrantClient
        
        if embeddings is None:
            print("⚠️  RAG system not ready, fallback to keyword search...")
            return await search_memory(query, top_k)
        
        # 🆕 Phase 26: Create vector store adapter (Phase 25 pattern)
        cfg = load_config()
        dim = cfg.get("embeddings_dim", 384)
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        try:
            client = QdrantClient(url=url, api_key=api_key)
            adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        except Exception as e:
            print(f"⚠️  Failed to create Qdrant adapter: {e}, fallback to keyword search...")
            return await search_memory(query, top_k)
        
        # 🆕 Phase 26.1: Build Qdrant filters from parameters
        # Note: Native Qdrant filtering will be added in future phase
        # For now, we use post-search filtering
        
        # Perform similarity search with more candidates for reranking and filtering
        initial_k = top_k * 3 if reranker else top_k
        
        # Get similarity search results with scores
        docs_with_scores = adapter.similarity_search_with_score(query, k=initial_k * 2)
        
        # 🆕 Phase 26.1: Filter results based on metadata
        filtered_docs = []
        for doc, score in docs_with_scores:
            meta = doc.metadata
            # Apply filters
            if min_importance is not None and meta.get("importance", 0) < min_importance:
                continue
            if emotion and meta.get("emotion") != emotion:
                continue
            if action_tag and meta.get("action_tag") != action_tag:
                continue
            if environment and meta.get("environment") != environment:
                continue
            if physical_state and meta.get("physical_state") != physical_state:
                continue
            if mental_state and meta.get("mental_state") != mental_state:
                continue
            if relationship_status and meta.get("relationship_status") != relationship_status:
                continue
            
            # 🆕 Phase 26.2: Calculate custom score
            final_score = score  # Base vector similarity score
            
            if importance_weight > 0 and meta.get("importance") is not None:
                final_score += importance_weight * meta["importance"]
            
            if recency_weight > 0 and meta.get("created_at"):
                from datetime import datetime
                try:
                    created_at = datetime.fromisoformat(meta["created_at"])
                    now = datetime.now()
                    days_ago = (now - created_at).days
                    # Recency score: 1.0 for today, decreases over time (0 after 1 year)
                    recency_score = max(0, 1 - days_ago / 365.0)
                    final_score += recency_weight * recency_score
                except:
                    pass
            
            doc.metadata["final_score"] = final_score
            filtered_docs.append((doc, final_score))
        
        # Sort by final score (descending)
        filtered_docs.sort(key=lambda x: x[1], reverse=True)
        docs = [doc for doc, score in filtered_docs[:initial_k]]
        
        # Rerank if reranker is available
        if reranker and docs:
            # Prepare query-document pairs for reranking
            pairs = [[query, doc.page_content] for doc in docs]
            # Get reranking scores
            scores = reranker.predict(pairs)
            # Sort documents by score (descending)
            ranked_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
            # Take top_k after reranking
            docs = [doc for doc, score in ranked_docs[:top_k]]
        else:
            # If no reranker, just take top_k from similarity search
            docs = docs[:top_k]
        
        if docs:
            # Build filter description for display
            filter_desc = []
            if min_importance is not None:
                filter_desc.append(f"importance≥{min_importance}")
            if emotion:
                filter_desc.append(f"emotion={emotion}")
            if action_tag:
                filter_desc.append(f"action={action_tag}")
            if environment:
                filter_desc.append(f"env={environment}")
            if physical_state:
                filter_desc.append(f"physical={physical_state}")
            if mental_state:
                filter_desc.append(f"mental={mental_state}")
            if relationship_status:
                filter_desc.append(f"relation={relationship_status}")
            
            filter_str = f" [filters: {', '.join(filter_desc)}]" if filter_desc else ""
            
            # Build scoring description
            scoring_desc = []
            if importance_weight > 0:
                scoring_desc.append(f"importance×{importance_weight}")
            if recency_weight > 0:
                scoring_desc.append(f"recency×{recency_weight}")
            
            scoring_str = f" [scoring: vector + {' + '.join(scoring_desc)}]" if scoring_desc else ""
            
            result = f"🔍 Found {len(docs)} relevant memories for '{query}'{filter_str}{scoring_str}:\n\n"
            persona = get_current_persona()
            db_path = get_db_path()
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                for i, doc in enumerate(docs, 1):
                    key = doc.metadata.get("key", "unknown")
                    content = doc.page_content
                    # DBからメタデータ取得（全12フィールド）
                    cursor.execute('''
                        SELECT created_at, importance, emotion, physical_state, 
                               mental_state, environment, relationship_status, action_tag 
                        FROM memories WHERE key = ?
                    ''', (key,))
                    row = cursor.fetchone()
                    if row:
                        created_at, importance, emotion_db, physical, mental, env, relation, action = row
                        created_date = created_at[:10]
                        created_time = created_at[11:19]
                        time_diff = calculate_time_diff(created_at)
                        time_ago = f" ({time_diff['formatted_string']}前)"
                        
                        # Build metadata display
                        meta_parts = []
                        if importance is not None and importance != 0.5:
                            meta_parts.append(f"⭐{importance:.1f}")
                        if emotion_db and emotion_db != "neutral":
                            meta_parts.append(f"😊{emotion_db}")
                        if action:
                            meta_parts.append(f"🎭{action}")
                        if env and env != "unknown":
                            meta_parts.append(f"📍{env}")
                        
                        meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""
                        
                        # Show final score if custom scoring was used
                        score_str = ""
                        if importance_weight > 0 or recency_weight > 0:
                            final_score = doc.metadata.get("final_score")
                            if final_score is not None:
                                score_str = f" (score: {final_score:.3f})"
                    else:
                        created_date = "unknown"
                        created_time = "unknown"
                        time_ago = ""
                        meta_str = ""
                        score_str = ""
                    
                    result += f"{i}. [{key}]{meta_str}{score_str}\n"
                    result += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n"
                    result += f"   {created_date} {created_time}{time_ago} ({len(content)} chars)\n\n"
            return result.rstrip()
        else:
            filter_desc = []
            if min_importance is not None:
                filter_desc.append(f"importance≥{min_importance}")
            if emotion:
                filter_desc.append(f"emotion={emotion}")
            if action_tag:
                filter_desc.append(f"action={action_tag}")
            filter_str = f" (filters: {', '.join(filter_desc)})" if filter_desc else ""
            return f"No relevant memories found for '{query}'{filter_str}."
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Failed to search memories with RAG: {str(e)}"

