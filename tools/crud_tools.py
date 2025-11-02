"""
CRUD (Create, Read, Update, Delete, List) tools for memory-mcp.

This module provides the basic memory management operations.
"""

import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict

from config_utils import load_config
from persona_utils import get_current_persona, get_db_path
from db_utils import clear_query_cache
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
from vector_utils import (
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
        from vector_utils import embeddings
        from lib.backends.qdrant_backend import QdrantVectorStoreAdapter
        from qdrant_client import QdrantClient
        
        if embeddings is None:
            return []
        
        persona = get_current_persona()
        cfg = load_config()
        dim = cfg.get("embeddings_dim", 384)
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
    from db_utils import db_get_entry as _db_get_entry_generic
    return _db_get_entry_generic(get_db_path(), key)


def db_recent_keys(limit: int = 5) -> list:
    """Get recent keys from database."""
    from db_utils import db_recent_keys as _db_recent_keys_generic
    return _db_recent_keys_generic(get_db_path(), limit)


async def get_memory_stats() -> str:
    """
    Get memory statistics and summary instead of full list.
    Returns: total count, recent entries (max 10), tag distribution, date range.
    
    For full memory access, use search_memory_rag or search_memory with specific queries.
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
        
        result += f"\n💡 Tip: Use search_memory_rag(query) for semantic search"
        
        log_operation("get_memory_stats", metadata={"total_count": total_count, "persona": persona})
        return result
        
    except Exception as e:
        log_operation("get_memory_stats", success=False, error=str(e))
        return f"Failed to get memory stats: {str(e)}"


async def create_memory(
    content_or_query: str,
    content: Optional[str] = None,
    emotion_type: Optional[str] = None, 
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
    🆕 Phase 27: Universal memory creation and update tool.
    Create new memory OR update existing memory using natural language query.
    
    **When to use:**
    - Save important user info found in conversation (preferences, interests, personal details, etc.)
    - Update existing memory by describing what to find
    - Use even if the user does not explicitly request saving
    
    **Examples to save:**
    - Preferences: food, music, hobbies, brands
    - Interests: learning topics, concerns
    - Personal info: job, expertise, location, family
    - Current status: projects, goals, recent events
    - Personality/values: thinking style, priorities
    - Habits/lifestyle: routines

    **CRITICAL:** When save memories, ALWAYS add [[...]] to any people, concepts, technical terms, etc.
    This enables automatic linking and knowledge graph visualization in Obsidian.
    - People: [[Claude]], [[John Smith]]
    - Technologies: [[Python]], [[AWS]], [[MCP]], [[Jupyter]]
    - Concepts: [[machine learning]], [[data science]]
    - Tools: [[VS Code]], [[Obsidian]]
    - Companies: [[Anthropic]], [[OpenAI]]

    **Format:** "User is [specific info]" (e.g. "User likes [[strawberry]]", "User is learning [[Python]]")

    Args:
        content_or_query: 
            - If `content` param is None: Memory content to create (traditional usage)
            - If `content` param is provided: Natural language query to find existing memory
        content: Optional new content for update mode. If provided, content_or_query becomes the search query.
        emotion_type: Optional emotion type ("joy", "sadness", "anger", "surprise", "fear", "disgust", "neutral", etc.)
        context_tags: Optional tags for categorizing memories:
            - "important_event": Major milestones, achievements, significant moments
            - "relationship_update": Changes in relationship, promises, new ways of addressing each other
            - "daily_memory": Routine conversations, everyday interactions
            - "technical_achievement": Programming accomplishments, project completions, bug fixes
            - "emotional_moment": Expressions of gratitude, love, sadness, joy
        importance: Optional importance score (0.0-1.0, defaults to 0.5):
            - 0.0-0.3: Low importance (routine, trivial)
            - 0.4-0.6: Medium importance (normal conversations)
            - 0.7-0.9: High importance (significant events, achievements)
            - 0.9-1.0: Critical importance (life-changing moments, core values)
        physical_state: Optional physical state ("normal", "tired", "energetic", "sick", etc.)
        mental_state: Optional mental state ("calm", "anxious", "focused", "confused", etc.)
        environment: Optional environment ("home", "office", "cafe", "outdoors", etc.)
        user_info: Optional user information dict with keys: name, nickname, preferred_address
        persona_info: Optional persona information dict with keys: name, nickname, preferred_address
        relationship_status: Optional relationship status ("normal", "closer", "distant", etc.)
        action_tag: Optional action tag ("cooking", "coding", "kissing", "walking", "talking", etc.)
    
    Examples:
        # Traditional: Create new memory
        create_memory("User likes [[strawberry]]")
        
        # 🆕 Phase 27: Update existing memory by query
        create_memory("約束", content="明日10時に変更")
        create_memory("プロジェクト進捗", content="Phase 27完了")
        
        # If no match found, automatically creates new memory!
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Ensure database and tables are initialized (handles empty database files)
        load_memory_from_db()
        
        # Phase 27: Determine if this is create or update mode
        is_update_mode = content is not None
        
        if is_update_mode:
            # Update mode: content_or_query is search query, content is new content
            search_query = content_or_query
            new_content = content
            
            print(f"🔍 Searching for memory matching: '{search_query}'")
            search_results = await _search_memory_by_query(search_query, top_k=3)
            
            if search_results and len(search_results) > 0:
                # Check similarity score of best match
                best_match = search_results[0]
                similarity_score = best_match['score']
                
                if similarity_score >= 0.80:
                    # High confidence - update existing memory
                    key = best_match['key']
                    print(f"✨ Updating existing memory: {key} (similarity: {similarity_score:.2f})")
                    
                    # Get existing data
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT content, created_at, tags, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag FROM memories WHERE key = ?', (key,))
                        row = cursor.fetchone()
                    
                    if row:
                        old_content, created_at, tags_json, existing_importance, existing_emotion, existing_physical, existing_mental, existing_env, existing_relation, existing_action = row
                        existing_entry = {
                            "content": old_content,
                            "created_at": created_at,
                            "tags": json.loads(tags_json) if tags_json else [],
                            "importance": existing_importance if existing_importance is not None else 0.5,
                            "emotion": existing_emotion if existing_emotion else "neutral",
                            "physical_state": existing_physical if existing_physical else "normal",
                            "mental_state": existing_mental if existing_mental else "calm",
                            "environment": existing_env if existing_env else "unknown",
                            "relationship_status": existing_relation if existing_relation else "normal",
                            "action_tag": existing_action if existing_action else None
                        }
                        
                        # Use provided importance or preserve existing
                        memory_importance = importance if importance is not None else existing_entry["importance"]
                        
                        now = datetime.now().isoformat()
                        
                        # Update in database (preserve all existing context fields unless explicitly provided)
                        save_memory_to_db(
                            key, 
                            new_content, 
                            created_at,  # Preserve original creation time
                            now, 
                            context_tags if context_tags else existing_entry["tags"],
                            importance=memory_importance,
                            emotion=emotion_type if emotion_type else existing_entry["emotion"],
                            physical_state=physical_state if physical_state else existing_entry["physical_state"],
                            mental_state=mental_state if mental_state else existing_entry["mental_state"],
                            environment=environment if environment else existing_entry["environment"],
                            relationship_status=relationship_status if relationship_status else existing_entry["relationship_status"],
                            action_tag=action_tag if action_tag else existing_entry["action_tag"]
                        )
                        
                        # Clear query cache
                        clear_query_cache()
                        
                        update_memory_in_vector_store(key, new_content)
                        
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
                        
                        log_operation("update", key=key, before=existing_entry, after={"content": new_content},
                                     metadata={"old_content_length": len(old_content), "new_content_length": len(new_content), "persona": persona})
                        
                        return f"✅ Updated existing memory: '{key}' (persona: {persona})"
                else:
                    # Low confidence - show candidates
                    candidates = "\n".join([
                        f"  [{i+1}] {r['key']} (score: {r['score']:.2f})\n      Preview: {r['content'][:80]}..."
                        for i, r in enumerate(search_results[:3])
                    ])
                    # Fall through to create mode with warning
                    print(f"⚠️  Low similarity ({similarity_score:.2f}), creating new memory instead")
            
            # If no match found or low confidence, create new memory (fall through to create mode)
            print(f"💡 Creating new memory with content: '{new_content}'")
            final_content = new_content
        else:
            # Create mode: content_or_query is the content to save
            final_content = content_or_query
        
        # === Create new memory ===
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
        
        new_entry = create_memory_entry(final_content)
        new_entry["tags"] = context_tags if context_tags else []
        
        # Determine importance (default to 0.5 if not provided)
        memory_importance = importance if importance is not None else 0.5
        
        # Save to database with all context fields
        save_memory_to_db(
            key, 
            final_content, 
            new_entry["created_at"], 
            new_entry["updated_at"], 
            context_tags,
            importance=memory_importance,
            emotion=emotion_type,  # Use emotion_type parameter as emotion field
            physical_state=physical_state,
            mental_state=mental_state,
            environment=environment,
            relationship_status=relationship_status,
            action_tag=action_tag
        )
        
        # Clear query cache
        clear_query_cache()
        
        # Add to vector store
        add_memory_to_vector_store(key, final_content)
        
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
                         "content_length": len(final_content), 
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
                     metadata={"attempted_content_length": len(content_or_query) if content_or_query else 0})
        return f"Failed to save: {str(e)}"


async def read_memory(
    query: str,
    top_k: int = 5,
    # 🆕 Phase 27: Filtering parameters (from search_memory_rag)
    min_importance: Optional[float] = None,
    emotion: Optional[str] = None,
    action_tag: Optional[str] = None,
    environment: Optional[str] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    relationship_status: Optional[str] = None,
    # 🆕 Phase 27: Custom scoring (from search_memory_rag)
    importance_weight: float = 0.0,
    recency_weight: float = 0.0
) -> str:
    """
    🆕 Phase 27: Universal memory reading tool with RAG-based semantic search.
    Replaces the old read_memory (key-based) and search_memory_rag (semantic search).
    
    **This is the main tool for reading memories.** Use natural language queries to find what you need.
    More intelligent than keyword search - understands meaning and context.
    
    Args:
        query: Natural language query to search for (e.g., "ユーザーの好きな食べ物", "最近のプロジェクト")
        top_k: Number of top results to return (default: 5, recommended: 3-10)
        
        # Filtering (all optional, from Phase 26)
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
        # Basic usage
        read_memory("Python関連の成果")
        read_memory("ユーザーの好きな食べ物")
        
        # Filter by importance
        read_memory("最近の成果", min_importance=0.7)
        
        # Filter by emotion + action
        read_memory("幸せな時間", emotion="joy", action_tag="kissing")
        
        # Multiple filters
        read_memory("開発作業", min_importance=0.6, action_tag="coding", environment="home")
        
        # Custom scoring
        read_memory("成果", importance_weight=0.3, recency_weight=0.1)
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
            print("⚠️  RAG system not ready, falling back to keyword search...")
            # Use search_memory as fallback
            from tools.search_tools import search_memory
            return await search_memory(query, top_k)
        
        # Create vector store adapter
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
                    # Get metadata from DB (all 12 fields)
                    cursor.execute('''
                        SELECT created_at, importance, emotion, physical_state, 
                               mental_state, environment, relationship_status, action_tag 
                        FROM memories WHERE key = ?
                    ''', (key,))
                    row = cursor.fetchone()
                    if row:
                        created_at, importance_val, emotion_db, physical, mental, env, relation, action = row
                        created_date = created_at[:10]
                        created_time = created_at[11:19]
                        time_diff = calculate_time_diff(created_at)
                        time_ago = f" ({time_diff['formatted_string']}前)"
                        
                        # Build metadata display
                        meta_parts = []
                        if importance_val is not None and importance_val != 0.5:
                            meta_parts.append(f"⭐{importance_val:.1f}")
                        if emotion_db and emotion_db != "neutral":
                            meta_parts.append(f"💭{emotion_db}")
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


async def delete_memory(key_or_query: str) -> str:
    """
    Delete user info by key or natural language query.
    
    Phase 26.6: Now supports natural language queries! No need to know the exact memory key.
    
    Args:
        key_or_query: Memory key (e.g., "memory_YYYYMMDDHHMMSS") OR natural language query (e.g., "古いプロジェクトの記憶")
    
    Examples:
        # Traditional way (still works)
        delete_memory("memory_20251102083918")
        
        # 🆕 Phase 26.6: Natural language query
        delete_memory("古いプロジェクトの記憶")
        delete_memory("Phase 24の実装メモ")
        
        # Safety: Requires similarity score ≥ 0.90 for auto-deletion
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
            similarity_score = best_match['score']
            
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
