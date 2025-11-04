"""
CRUD (Create, Read, Update, Delete, List) tools for memory-mcp.

This module provides the basic memory management operations.
"""

import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict

from src.utils.config_utils import load_config
from src.utils.persona_utils import get_current_persona, get_db_path
from src.utils.db_utils import clear_query_cache
from core import (
    calculate_time_diff,
    load_persona_context,
    save_persona_context,
    create_memory_entry,
    generate_auto_key,
    save_memory_to_db,
    delete_memory_from_db,
    load_memory_from_db,
    log_operation,
)
from src.utils.vector_utils import (
    add_memory_to_vector_store,
    update_memory_in_vector_store,
    delete_memory_from_vector_store,
)


# ============================================================
# Phase 26.6: Internal RAG Search Helper
# ============================================================

async def _search_memory_by_query(query: str, top_k: int = 3) -> List[Dict]:
    """
    Internal helper to search memories using RAG.
    Returns list of dicts with keys: 'key', 'content', 'score', 'metadata'
    
    This is used by update_memory, delete_memory, read_memory to enable
    natural language queries instead of requiring exact memory keys.
    """
    try:
        from src.utils.vector_utils import embeddings
        from lib.backends.qdrant_backend import QdrantVectorStoreAdapter
        from qdrant_client import QdrantClient
        
        if embeddings is None:
            return []
        
        persona = get_current_persona()
        cfg = load_config()
        
        # 🔧 Phase 31.2: Get correct dimension from model config
        model_name = cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m")
        from src.utils.vector_utils import _get_embedding_dimension
        dim = _get_embedding_dimension(model_name)
        
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        # Create Qdrant adapter
        client = QdrantClient(url=url, api_key=api_key)
        adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        
        # Perform similarity search
        docs_with_scores = adapter.similarity_search_with_score(query, k=top_k)
        
        # Format results
        results = []
        for doc, score in docs_with_scores:
            meta = doc.metadata
            results.append({
                'key': meta.get('key', ''),
                'content': doc.page_content,
                'score': score,
                'metadata': meta
            })
        
        return results
        
    except Exception as e:
        print(f"⚠️  RAG search failed: {e}")
        return []


def db_get_entry(key: str):
    """Get single entry from database."""
    from src.utils.db_utils import db_get_entry as _db_get_entry_generic
    return _db_get_entry_generic(get_db_path(), key)


def db_recent_keys(limit: int = 5) -> list:
    """Get recent keys from database."""
    from src.utils.db_utils import db_recent_keys as _db_recent_keys_generic
    return _db_recent_keys_generic(get_db_path(), limit)


async def get_memory_stats() -> str:
    """
    Get memory statistics and summary instead of full list.
    Returns: total count, recent entries (max 10), tag distribution, date range.
    
    For full memory access, use read_memory or search_memory with specific queries.
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Total count
            cursor.execute('SELECT COUNT(*) FROM memories')
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                return f"📊 No memories yet (persona: {persona})"
            
            # Total characters
            cursor.execute('SELECT SUM(LENGTH(content)) FROM memories')
            total_chars = cursor.fetchone()[0] or 0
            
            # Date range
            cursor.execute('SELECT MIN(created_at), MAX(created_at) FROM memories')
            min_date, max_date = cursor.fetchone()
            
            # Importance statistics
            cursor.execute('SELECT AVG(importance), MIN(importance), MAX(importance) FROM memories WHERE importance IS NOT NULL')
            importance_stats = cursor.fetchone()
            avg_importance = importance_stats[0] if importance_stats[0] is not None else 0.5
            min_importance = importance_stats[1] if importance_stats[1] is not None else 0.5
            max_importance = importance_stats[2] if importance_stats[2] is not None else 0.5
            
            # Importance distribution (high/medium/low)
            cursor.execute('SELECT COUNT(*) FROM memories WHERE importance >= 0.7')
            high_importance_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM memories WHERE importance >= 0.4 AND importance < 0.7')
            medium_importance_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM memories WHERE importance < 0.4')
            low_importance_count = cursor.fetchone()[0]
            
            # Emotion distribution
            cursor.execute('SELECT emotion, COUNT(*) FROM memories WHERE emotion IS NOT NULL GROUP BY emotion ORDER BY COUNT(*) DESC')
            emotion_counts = cursor.fetchall()
            
            # Recent 10 entries
            cursor.execute('SELECT key, content, created_at, importance, emotion FROM memories ORDER BY created_at DESC LIMIT 10')
            recent = cursor.fetchall()
            
            # Tag distribution
            cursor.execute('SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != "[]"')
            all_tags = []
            for (tags_json,) in cursor.fetchall():
                try:
                    tags = json.loads(tags_json)
                    all_tags.extend(tags)
                except:
                    pass
            
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
        # Build result
        result = f"📊 Memory Statistics (persona: {persona})\n\n"
        result += f"📈 Total Memories: {total_count}\n"
        result += f"📝 Total Characters: {total_chars:,}\n"
        result += f"📅 Date Range: {min_date[:10]} ~ {max_date[:10]}\n\n"
        
        result += f"⭐ Importance Statistics:\n"
        result += f"   Average: {avg_importance:.2f}\n"
        result += f"   Range: {min_importance:.2f} ~ {max_importance:.2f}\n"
        result += f"   High (≥0.7): {high_importance_count}\n"
        result += f"   Medium (0.4~0.7): {medium_importance_count}\n"
        result += f"   Low (<0.4): {low_importance_count}\n\n"
        
        if emotion_counts:
            result += "💭 Emotion Distribution:\n"
            for emotion, count in emotion_counts[:10]:  # Top 10 emotions
                result += f"   {emotion}: {count}\n"
            result += "\n"
        
        if tag_counts:
            result += "🏷️  Tag Distribution:\n"
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
            for tag, count in sorted_tags[:10]:  # Top 10 tags
                result += f"   {tag}: {count}\n"
            result += "\n"
        
        result += f"🕐 Recent {len(recent)} Memories:\n"
        for i, (key, content, created_at, importance, emotion) in enumerate(recent, 1):
            preview = content[:60] + "..." if len(content) > 60 else content
            created_date = created_at[:10]
            time_diff = calculate_time_diff(created_at)
            importance_str = f"{importance:.2f}" if importance is not None else "0.50"
            emotion_str = emotion if emotion else "neutral"
            result += f"{i}. [{key}] {preview}\n"
            result += f"   {created_date} ({time_diff['formatted_string']}前) | Importance: {importance_str} | Emotion: {emotion_str}\n"
        
        result += f"\n💡 Tip: Use read_memory(query) for semantic search"
        
        log_operation("get_memory_stats", metadata={"total_count": total_count, "persona": persona})
        return result
        
    except Exception as e:
        log_operation("get_memory_stats", success=False, error=str(e))
        return f"Failed to get memory stats: {str(e)}"


async def create_memory(
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
    """
    Create new memory (fast - no RAG search). For updates, use update_memory().
    
    **When to use this tool:**
    - User shares new information (preferences, facts, experiences)
    - User makes a promise or sets a goal
    - Important events or achievements occur
    - User expresses feelings or emotions worth remembering
    - New relationships or status changes
    
    **When NOT to use:**
    - Updating existing information → use update_memory()
    - Just searching for info → use read_memory()
    - General conversation without new facts
    
    **RULES:**
    1. Write in SAME language as conversation (日本語 ↔ 日本語)
    2. Add [[links]] for people, tech, concepts ([[Python]], [[Alice]], [[VS Code]])
    
    Args:
        content: Memory content (required)
        emotion_type: "joy", "love", "neutral", etc.
        context_tags: ["important_event", "technical_achievement", "emotional_moment", etc.]
        importance: 0.0-1.0 (0.7+ = high, 0.4-0.7 = medium, <0.4 = low)
        physical_state, mental_state, environment, relationship_status, action_tag: Optional context
        user_info/persona_info: Dicts with name, nickname, preferred_address
    
    Examples:
        create_memory("User likes [[strawberry]]")
        create_memory("[[Python]] project completed", importance=0.8, context_tags=["technical_achievement"])
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Ensure database and tables are initialized (handles empty database files)
        load_memory_from_db()
        
        # === Create new memory (simple and fast) ===
        # Generate unique key by checking database
        key = generate_auto_key()
        original_key = key
        counter = 1
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Check if key exists in database
            while True:
                cursor.execute('SELECT COUNT(*) FROM memories WHERE key = ?', (key,))
                if cursor.fetchone()[0] == 0:
                    break
                key = f"{original_key}_{counter:02d}"
                counter += 1
        
        new_entry = create_memory_entry(content)
        new_entry["tags"] = context_tags if context_tags else []
        
        # Determine importance (default to 0.5 if not provided)
        memory_importance = importance if importance is not None else 0.5
        
        # Phase 28.2: Generate associations and adjust importance
        from tools.association import generate_associations
        
        emotion_intensity_value = emotion_intensity if emotion_intensity is not None else 0.0
        related_keys, adjusted_importance = generate_associations(
            new_key=key,
            new_content=content,
            emotion_intensity=emotion_intensity_value,
            base_importance=memory_importance
        )
        
        # Use adjusted importance if no explicit importance was provided
        if importance is None:
            memory_importance = adjusted_importance
        
        # Save to database with all context fields
        save_memory_to_db(
            key, 
            content, 
            new_entry["created_at"], 
            new_entry["updated_at"], 
            context_tags,
            importance=memory_importance,
            emotion=emotion_type,  # Use emotion_type parameter as emotion field
            emotion_intensity=emotion_intensity_value,
            physical_state=physical_state,
            mental_state=mental_state,
            environment=environment,
            relationship_status=relationship_status,
            action_tag=action_tag,
            related_keys=related_keys,  # Phase 28.2: Populated by association module
            summary_ref=None  # Phase 28.4: Will be populated by summarization module
        )
        
        # Clear query cache
        clear_query_cache()
        
        # Add to vector store
        add_memory_to_vector_store(key, content)
        
        # Update persona context if any context parameters are provided
        context_updated = False
        context = load_persona_context(persona)
        
        # Always update last_conversation_time
        config = load_config()
        context["last_conversation_time"] = datetime.now(ZoneInfo(config.get("timezone", "Asia/Tokyo"))).isoformat()
        context_updated = True
        
        # Update emotion if provided
        if emotion_type:
            context["current_emotion"] = emotion_type
            context_updated = True
        
        # Update physical state if provided
        if physical_state:
            context["physical_state"] = physical_state
            context_updated = True
        
        # Update mental state if provided
        if mental_state:
            context["mental_state"] = mental_state
            context_updated = True
        
        # Update environment if provided
        if environment:
            context["environment"] = environment
            context_updated = True
        
        # Update user info if provided
        if user_info:
            if "user_info" not in context:
                context["user_info"] = {}
            for key_name, value in user_info.items():
                if key_name in ["name", "nickname", "preferred_address"]:
                    context["user_info"][key_name] = value
            context_updated = True
        
        # Update persona info if provided
        if persona_info:
            if "persona_info" not in context:
                context["persona_info"] = {}
            for key_name, value in persona_info.items():
                if key_name in ["name", "nickname", "preferred_address"]:
                    context["persona_info"][key_name] = value
            context_updated = True
        
        # Update relationship status if provided
        if relationship_status:
            context["relationship_status"] = relationship_status
            context_updated = True
        
        if context_updated:
            save_persona_context(context, persona)
        
        log_operation("create", key=key, after=new_entry, 
                     metadata={
                         "content_length": len(content), 
                         "auto_generated_key": key, 
                         "persona": persona,
                         "emotion_type": emotion_type,
                         "context_tags": context_tags,
                         "physical_state": physical_state,
                         "mental_state": mental_state,
                         "environment": environment,
                         "user_info": user_info,
                         "persona_info": persona_info,
                         "relationship_status": relationship_status
                     })
        
        result = f"✅ Created new memory: '{key}' (persona: {persona})"
        if emotion_type:
            result += f" [emotion: {emotion_type}]"
        if context_tags:
            result += f" [tags: {', '.join(context_tags)}]"
        if context_updated:
            result += " [context updated]"
        
        return result
    except Exception as e:
        log_operation("create", success=False, error=str(e), 
                     metadata={"attempted_content_length": len(content) if content else 0})
        return f"Failed to save: {str(e)}"


async def read_memory(
    query: str,
    top_k: int = 5,
    # Filtering parameters
    min_importance: Optional[float] = None,
    emotion: Optional[str] = None,
    action_tag: Optional[str] = None,
    environment: Optional[str] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    relationship_status: Optional[str] = None,
    # Custom scoring
    importance_weight: float = 0.0,
    recency_weight: float = 0.0
) -> str:
    """
    Main semantic search tool - understands meaning, not just keywords.
    
    **When to use this tool:**
    - Need to find information from past conversations
    - User asks "what did I say about X?"
    - Looking for related memories on a topic
    - Want memories matching certain emotions or context
    - Understanding user's preferences or history
    
    **When NOT to use:**
    - Creating new memories → use create_memory()
    - Exact keyword search → use search_memory()
    - Just need current context → already called get_context()
    
    Args:
        query: Natural language (e.g., "ユーザーの好きな食べ物", "recent achievements")
        top_k: Results to return (default: 5)
        min_importance: Filter by importance 0.0-1.0 (e.g., 0.7 for important only)
        emotion/action_tag/environment/physical_state/mental_state/relationship_status: Context filters
        importance_weight/recency_weight: Custom scoring (0.0-1.0)
    
    Examples:
        read_memory("Python関連")
        read_memory("成果", min_importance=0.7, importance_weight=0.3)
    """
    try:
        persona = get_current_persona()
        
        if not query:
            return "Please provide a query to search."
        
        # Check if RAG system is ready, fallback to keyword search if not
        from src.utils.vector_utils import embeddings, reranker
        from lib.backends.qdrant_backend import QdrantVectorStoreAdapter
        from qdrant_client import QdrantClient
        
        if embeddings is None:
            print("⚠️  RAG system not ready, falling back to keyword search...")
            # Use search_memory as fallback
            from tools.search_tools import search_memory
            return await search_memory(query, top_k)
        
        # Create vector store adapter
        cfg = load_config()
        
        # 🔧 Phase 31.2: Get correct dimension from model config
        model_name = cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m")
        from src.utils.vector_utils import _get_embedding_dimension
        dim = _get_embedding_dimension(model_name)
        
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        try:
            client = QdrantClient(url=url, api_key=api_key)
            adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        except Exception as e:
            print(f"⚠️  Failed to create Qdrant adapter: {e}, falling back to keyword search...")
            from tools.search_tools import search_memory
            return await search_memory(query, top_k)
        
        # Perform similarity search with more candidates for reranking and filtering
        initial_k = top_k * 3 if reranker else top_k
        
        # Get similarity search results with scores
        docs_with_scores = adapter.similarity_search_with_score(query, k=initial_k * 2)
        
        # Filter results based on metadata
        filtered_docs = []
        for doc, score in docs_with_scores:
            meta = doc.metadata
            # Apply filters
            if min_importance is not None and meta.get("importance", 0) < min_importance:
                continue
            # Fuzzy matching for text filters (case-insensitive partial match)
            if emotion and emotion.lower() not in str(meta.get("emotion", "")).lower():
                continue
            if action_tag and action_tag.lower() not in str(meta.get("action_tag", "")).lower():
                continue
            if environment and environment.lower() not in str(meta.get("environment", "")).lower():
                continue
            if physical_state and physical_state.lower() not in str(meta.get("physical_state", "")).lower():
                continue
            if mental_state and mental_state.lower() not in str(meta.get("mental_state", "")).lower():
                continue
            if relationship_status and relationship_status.lower() not in str(meta.get("relationship_status", "")).lower():
                continue
            
            # Calculate custom score
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
            
            result = f"� Found {len(docs)} relevant memories for '{query}'{filter_str}{scoring_str}:\n\n"
            
            db_path = get_db_path()
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                for i, doc in enumerate(docs, 1):
                    key = doc.metadata.get("key", "unknown")
                    content = doc.page_content
                    # Get metadata from DB (including Phase 28 fields)
                    cursor.execute('''
                        SELECT created_at, importance, emotion, emotion_intensity,
                               physical_state, mental_state, environment, 
                               relationship_status, action_tag, related_keys
                        FROM memories WHERE key = ?
                    ''', (key,))
                    row = cursor.fetchone()
                    if row:
                        created_at, importance_val, emotion_db, emotion_intensity_val, physical, mental, env, relation, action, related_keys_json = row
                        created_date = created_at[:10]
                        created_time = created_at[11:19]
                        time_diff = calculate_time_diff(created_at)
                        time_ago = f" ({time_diff['formatted_string']}前)"
                        
                        # Build metadata display
                        meta_parts = []
                        if importance_val is not None and importance_val != 0.5:
                            meta_parts.append(f"⭐{importance_val:.1f}")
                        if emotion_db and emotion_db != "neutral":
                            emotion_str = f"💭{emotion_db}"
                            # Add intensity if significant
                            if emotion_intensity_val and emotion_intensity_val >= 0.5:
                                emotion_str += f"({emotion_intensity_val:.1f})"
                            meta_parts.append(emotion_str)
                        if action:
                            meta_parts.append(f"🎭{action}")
                        if env and env != "unknown":
                            meta_parts.append(f"📍{env}")
                        
                        # Phase 28.2: Show related memories count
                        if related_keys_json:
                            try:
                                related_keys_list = json.loads(related_keys_json)
                                if related_keys_list:
                                    meta_parts.append(f"🔗{len(related_keys_list)}")
                            except:
                                pass
                        
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
            
            log_operation("read", key=query, metadata={"results_count": len(docs), "persona": persona})
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
            
            log_operation("read", key=query, success=False, error="No results")
            return f"📭 No relevant memories found for '{query}'{filter_str}."
    except Exception as e:
        import traceback
        traceback.print_exc()
        log_operation("read", key=query, success=False, error=str(e))
        return f"Failed to read memories: {str(e)}"


async def update_memory(
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
    """
    Update existing memory via natural language query (RAG search, threshold: 0.80).
    
    **When to use this tool:**
    - User changes a previous statement or preference
    - Updating status of ongoing tasks/projects
    - Modifying promises or appointments
    - Correcting previously saved information
    - Task completion or progress updates
    
    **When NOT to use:**
    - Saving completely new information → use create_memory()
    - Just searching → use read_memory()
    - If you know exact memory key → provide key in query
    
    Args:
        query: Natural language to find memory (e.g., "promise", "project progress")
        content: New content to replace
        (other params same as create_memory)
    
    Examples:
        update_memory("promise", "Changed to tomorrow 10am")
        update_memory("project", "Feature completed", importance=0.8)
    
    Note: If similarity < 0.80, shows candidates and creates new memory instead.
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Ensure database and tables are initialized
        load_memory_from_db()
        
        print(f"🔍 Searching for memory matching: '{query}'")
        search_results = await _search_memory_by_query(query, top_k=3)
        
        if not search_results or len(search_results) == 0:
            # No results - create new memory instead
            print(f"💡 No matching memory found. Creating new memory instead.")
            return await create_memory(
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
        
        # Check similarity score of best match
        best_match = search_results[0]
        similarity_score = best_match['score']  # Higher is better (1.0 = perfect match)
        
        if similarity_score < 0.80:
            # Low confidence - show candidates and create new
            candidates = "\n".join([
                f"  [{i+1}] {r['key']} (score: {r['score']:.2f})\n      Preview: {r['content'][:80]}..."
                for i, r in enumerate(search_results[:3])
            ])
            print(f"⚠️  Low similarity ({similarity_score:.2f}), creating new memory instead")
            print(f"📋 Candidates found:\n{candidates}")
            
            return await create_memory(
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
        
        # High confidence - update existing memory
        key = best_match['key']
        print(f"✨ Updating existing memory: {key} (similarity: {similarity_score:.2f})")
        
        # Get existing data
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content, created_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref FROM memories WHERE key = ?', (key,))
            row = cursor.fetchone()
        
        if not row:
            return f"❌ Memory key '{key}' not found in database"
        
        old_content, created_at, tags_json, existing_importance, existing_emotion, existing_emotion_intensity, existing_physical, existing_mental, existing_env, existing_relation, existing_action, existing_related_keys_json, existing_summary_ref = row
        existing_entry = {
            "content": old_content,
            "created_at": created_at,
            "tags": json.loads(tags_json) if tags_json else [],
            "importance": existing_importance if existing_importance is not None else 0.5,
            "emotion": existing_emotion if existing_emotion else "neutral",
            "emotion_intensity": existing_emotion_intensity if existing_emotion_intensity is not None else 0.0,
            "physical_state": existing_physical if existing_physical else "normal",
            "mental_state": existing_mental if existing_mental else "calm",
            "environment": existing_env if existing_env else "unknown",
            "relationship_status": existing_relation if existing_relation else "normal",
            "action_tag": existing_action if existing_action else None,
            "related_keys": json.loads(existing_related_keys_json) if existing_related_keys_json else [],
            "summary_ref": existing_summary_ref if existing_summary_ref else None
        }
        
        # Use provided importance or preserve existing
        memory_importance = importance if importance is not None else existing_entry["importance"]
        
        now = datetime.now().isoformat()
        
        # Update in database (preserve all existing context fields unless explicitly provided)
        save_memory_to_db(
            key, 
            content, 
            created_at,  # Preserve original creation time
            now, 
            context_tags if context_tags else existing_entry["tags"],
            importance=memory_importance,
            emotion=emotion_type if emotion_type else existing_entry["emotion"],
            emotion_intensity=emotion_intensity if emotion_intensity is not None else existing_entry.get("emotion_intensity", 0.0),
            physical_state=physical_state if physical_state else existing_entry["physical_state"],
            mental_state=mental_state if mental_state else existing_entry["mental_state"],
            environment=environment if environment else existing_entry["environment"],
            relationship_status=relationship_status if relationship_status else existing_entry["relationship_status"],
            action_tag=action_tag if action_tag else existing_entry["action_tag"],
            related_keys=existing_entry.get("related_keys", []),  # Preserve existing associations
            summary_ref=existing_entry.get("summary_ref", None)  # Preserve existing summary ref
        )
        
        # Clear query cache
        clear_query_cache()
        
        update_memory_in_vector_store(key, content)
        
        # Update persona context if needed
        context_updated = False
        context = load_persona_context(persona)
        
        # Always update last_conversation_time
        config = load_config()
        context["last_conversation_time"] = datetime.now(ZoneInfo(config.get("timezone", "Asia/Tokyo"))).isoformat()
        context_updated = True
        
        # Update other context fields if provided
        if emotion_type:
            context["current_emotion"] = emotion_type
            context_updated = True
        if physical_state:
            context["physical_state"] = physical_state
            context_updated = True
        if mental_state:
            context["mental_state"] = mental_state
            context_updated = True
        if environment:
            context["environment"] = environment
            context_updated = True
        if user_info:
            if "user_info" not in context:
                context["user_info"] = {}
            for key_name, value in user_info.items():
                if key_name in ["name", "nickname", "preferred_address"]:
                    context["user_info"][key_name] = value
            context_updated = True
        if persona_info:
            if "persona_info" not in context:
                context["persona_info"] = {}
            for key_name, value in persona_info.items():
                if key_name in ["name", "nickname", "preferred_address"]:
                    context["persona_info"][key_name] = value
            context_updated = True
        if relationship_status:
            context["relationship_status"] = relationship_status
            context_updated = True
        
        if context_updated:
            save_persona_context(context, persona)
        
        log_operation("update", key=key, before=existing_entry, after={"content": content},
                     metadata={"old_content_length": len(old_content), "new_content_length": len(content), "persona": persona})
        
        return f"✅ Updated existing memory: '{key}' (persona: {persona})"
    except Exception as e:
        import traceback
        traceback.print_exc()
        log_operation("update", success=False, error=str(e))
        return f"Failed to update memory: {str(e)}"


async def delete_memory(key_or_query: str) -> str:
    """
    Delete memory by exact key or natural language query.
    
    **When to use this tool:**
    - User explicitly asks to forget or delete something
    - Removing outdated or incorrect information
    - Cleaning up duplicate memories
    - User wants to remove sensitive information
    
    **When NOT to use:**
    - User just wants to update info → use update_memory()
    - Normal conversation → don't delete randomly
    - Uncertain about what to delete → ask user first
    
    Args:
        key_or_query: Memory key ("memory_YYYYMMDDHHMMSS") OR natural language query
    
    Examples:
        delete_memory("memory_20251102083918")
        delete_memory("古いプロジェクトの記憶")
    
    Safety: Natural language requires similarity ≥ 0.90 for auto-deletion.
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Phase 26.6: Check if input is a key or a query
        if key_or_query.startswith("memory_"):
            # Direct key access (traditional behavior)
            key = key_or_query
        else:
            # Natural language query - use RAG search
            print(f"🔍 Searching for memory to delete: '{key_or_query}'")
            search_results = await _search_memory_by_query(key_or_query, top_k=3)
            
            if not search_results or len(search_results) == 0:
                return f"❌ No matching memory found for query: '{key_or_query}'"
            
            # Check similarity score of best match
            best_match = search_results[0]
            similarity_score = best_match['score']  # Higher is better (1.0 = perfect match)
            
            if similarity_score >= 0.90:
                # Very high confidence - auto-select (strict threshold for deletion safety)
                key = best_match['key']
                print(f"✨ Auto-selected for deletion: {key} (similarity: {similarity_score:.2f})")
            else:
                # Lower confidence - show candidates for confirmation
                candidates = "\n".join([
                    f"  [{i+1}] {r['key']} (score: {r['score']:.2f})\n      Preview: {r['content'][:80]}..."
                    for i, r in enumerate(search_results[:3])
                ])
                return f"⚠️  Multiple candidates found. Please confirm by specifying exact key:\n\n{candidates}\n\n(Safety: Auto-deletion requires similarity ≥ 0.90)"
        
        # Check if key exists and get data
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content FROM memories WHERE key = ?', (key,))
            row = cursor.fetchone()
        
        if row:
            deleted_content = row[0]
            deleted_entry = {"content": deleted_content}
            
            delete_memory_from_db(key)
            
            # Clear query cache
            clear_query_cache()
            
            delete_memory_from_vector_store(key)
            
            log_operation("delete", key=key, before=deleted_entry,
                         metadata={"deleted_content_length": len(deleted_content), "persona": persona})
            
            return f"Deleted '{key}' (persona: {persona})"
        else:
            log_operation("delete", key=key, success=False, error="Key not found")
            # Get available keys
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key FROM memories ORDER BY created_at DESC LIMIT 5')
                available_keys = [r[0] for r in cursor.fetchall()]
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
    except Exception as e:
        log_operation("delete", key=key, success=False, error=str(e))
        return f"Failed to delete memory: {str(e)}"
