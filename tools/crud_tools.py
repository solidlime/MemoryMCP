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
    content: str, 
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
    Create new memory with important user info (preferences, interests, personal details, current status, etc.) found in conversation. Use even if the user does not explicitly request saving.
    If you find the memory is time sensitive, add time span into it.
    
    Examples to save:
    - Preferences: food, music, hobbies, brands
    - Interests: learning topics, concerns
    - Personal info: job, expertise, location, family
    - Current status: projects, goals, recent events
    - Personality/values: thinking style, priorities
    - Habits/lifestyle: routines

    CRITICAL: When save memories, ALWAYS add [[...]] to any people, concepts, technical terms, etc.
    This enables automatic linking and knowledge graph visualization in Obsidian.
    - People: [[Claude]], [[John Smith]]
    - Technologies: [[Python]], [[AWS]], [[MCP]], [[Jupyter]]
    - Concepts: [[machine learning]], [[data science]]
    - Tools: [[VS Code]], [[Obsidian]]
    - Companies: [[Anthropic]], [[OpenAI]]

    Format: "User is [specific info]" (e.g. "User likes [[strawberry]]", "User is learning [[Python]]", "User interested in [[AI]] in July 2025")

    Args:
        content: User info in "User is..." format.
        emotion_type: Optional emotion type ("joy", "sadness", "anger", "surprise", "fear", "disgust", "neutral", etc.) to update persona context
        context_tags: Optional tags for categorizing memories. Predefined tags:
            - "important_event": Major milestones, achievements, significant moments
            - "relationship_update": Changes in relationship, promises, new ways of addressing each other
            - "daily_memory": Routine conversations, everyday interactions
            - "technical_achievement": Programming accomplishments, project completions, bug fixes
            - "emotional_moment": Expressions of gratitude, love, sadness, joy
            Note: Tags are saved with the memory for future search and analysis. You can also use custom tags freely.
        importance: Optional importance score (0.0-1.0, defaults to 0.5). Higher values indicate more important memories.
            - 0.0-0.3: Low importance (routine, trivial)
            - 0.4-0.6: Medium importance (normal conversations)
            - 0.7-0.9: High importance (significant events, achievements)
            - 0.9-1.0: Critical importance (life-changing moments, core values)
        physical_state: Optional physical state ("normal", "tired", "energetic", "sick", etc.) to update persona context
        mental_state: Optional mental state ("calm", "anxious", "focused", "confused", etc.) to update persona context
        environment: Optional environment ("home", "office", "cafe", "outdoors", etc.) to update persona context
        user_info: Optional user information dict with keys: name, nickname, preferred_address
        persona_info: Optional persona information dict with keys: name, nickname, preferred_address
        relationship_status: Optional relationship status ("normal", "closer", "distant", etc.) to update persona context
        action_tag: Optional action tag describing what was happening during this memory creation
            Examples: "cooking", "coding", "kissing", "walking", "talking", "studying", "gaming", "exercising", etc.
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Ensure database and tables are initialized (handles empty database files)
        load_memory_from_db()
        
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
        
        # Save to database with all context fields
        save_memory_to_db(
            key, 
            content, 
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
        
        result = f"Saved: '{key}' (persona: {persona})"
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


async def read_memory(key: str) -> str:
    """
    Read user info by key.
    Args:
        key: Memory key (memory_YYYYMMDDHHMMSS)
    """
    try:
        persona = get_current_persona()
        # Read directly from database via helper
        row = db_get_entry(key)
        
        if row:
            content, created_at, updated_at, tags_json, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag = row
            
            # Calculate time elapsed since creation
            time_diff = calculate_time_diff(created_at)
            time_ago = f"{time_diff['formatted_string']}前"
            
            # Format all fields
            importance_str = f"{importance:.2f}" if importance is not None else "0.50"
            emotion_str = emotion if emotion else "neutral"
            physical_str = physical_state if physical_state else "normal"
            mental_str = mental_state if mental_state else "calm"
            env_str = environment if environment else "unknown"
            relation_str = relationship_status if relationship_status else "normal"
            action_str = action_tag if action_tag else "―"
            
            log_operation("read", key=key, metadata={"content_length": len(content), "persona": persona})
            result = f"""Key: '{key}' (persona: {persona})
{content}
--- Metadata ---
Created: {created_at} ({time_ago})
Updated: {updated_at}
Importance: {importance_str}
Emotion: {emotion_str}
Physical State: {physical_str}
Mental State: {mental_str}
Environment: {env_str}
Relationship: {relation_str}
Action: {action_str}
Chars: {len(content)}"""
            return result
        else:
            log_operation("read", key=key, success=False, error="Key not found")
            # Get available keys from DB
            available_keys = db_recent_keys(5)
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
    except Exception as e:
        log_operation("read", key=key, success=False, error=str(e))
        return f"Failed to read memory: {str(e)}"


async def update_memory(key: str, content: str, importance: Optional[float] = None) -> str:
    """
    Update existing memory content while preserving the original timestamp.
    Useful for consolidating or refining existing memories without losing temporal information.

    Args:
        key: Memory key to update (e.g., "memory_20250724225317")
        content: New content to replace the existing content
        importance: Optional importance score (0.0-1.0) to update. If not provided, preserves existing importance.
            - 0.0-0.3: Low importance (routine conversations, trivial information)
            - 0.4-0.6: Medium importance (normal conversations, general facts)
            - 0.7-0.9: High importance (significant events, important achievements)
            - 0.9-1.0: Critical importance (life-changing moments, core values)
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Check if key exists in database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content, created_at, tags, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag FROM memories WHERE key = ?', (key,))
            row = cursor.fetchone()
        
        if not row:
            log_operation("update", key=key, success=False, error="Key not found")
            # Get available keys
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key FROM memories ORDER BY created_at DESC LIMIT 5')
                available_keys = [r[0] for r in cursor.fetchall()]
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data exists."
        
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
        updated_entry = {
            "content": content,
            "created_at": created_at,
            "updated_at": now,
            "importance": memory_importance,
            "emotion": existing_entry["emotion"],  # Preserve existing emotion (update via create_memory if needed)
            "physical_state": existing_entry["physical_state"],
            "mental_state": existing_entry["mental_state"],
            "environment": existing_entry["environment"],
            "relationship_status": existing_entry["relationship_status"],
            "action_tag": existing_entry["action_tag"]
        }
        
        # Update in database (preserve all existing context fields)
        save_memory_to_db(
            key, 
            content, 
            created_at, 
            now, 
            existing_entry["tags"],
            importance=memory_importance,
            emotion=existing_entry["emotion"],
            physical_state=existing_entry["physical_state"],
            mental_state=existing_entry["mental_state"],
            environment=existing_entry["environment"],
            relationship_status=existing_entry["relationship_status"],
            action_tag=existing_entry["action_tag"]
        )
        
        # Clear query cache
        clear_query_cache()
        
        update_memory_in_vector_store(key, content)
        
        log_operation("update", key=key, before=existing_entry, after=updated_entry,
                     metadata={
                         "old_content_length": len(old_content),
                         "new_content_length": len(content),
                         "content_changed": old_content != content,
                         "persona": persona
                     })
        
        return f"Updated: '{key}' (persona: {persona})"
    except Exception as e:
        log_operation("update", key=key, success=False, error=str(e),
                     metadata={"attempted_content_length": len(content) if content else 0})
        return f"Failed to update memory: {str(e)}"


async def delete_memory(key: str) -> str:
    """
    Delete user info by key.
    Args:
        key: Memory key (memory_YYYYMMDDHHMMSS)
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
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
