"""
Persona context management tools for memory-mcp.

This module provides MCP tools for managing and querying persona context state.
"""

import json
import sqlite3
from core import (
    get_current_time,
    calculate_time_diff,
    load_persona_context,
    save_persona_context,
    log_operation,
)
from persona_utils import get_current_persona, get_db_path


def _log_progress(message: str) -> None:
    """Internal logging function."""
    print(message, flush=True)


async def get_session_context() -> str:
    """
    Get comprehensive session context for conversation startup.
    This single tool combines persona state, time tracking, and memory statistics.
    
    Use this at the beginning of each conversation session to understand:
    - Who the user is and current relationship status
    - How much time has passed since last conversation
    - What memories exist and their distribution
    
    Returns:
        Formatted string containing:
        - Persona context (user info, persona info, emotional/physical/mental states)
        - Time since last conversation (automatically updates last conversation time)
        - Memory statistics (count, recent entries, tag/emotion distribution)
    """
    try:
        persona = get_current_persona()
        
        # ===== PART 1: Persona Context =====
        context = load_persona_context(persona)
        
        result = f"📋 Session Context (persona: {persona})\n"
        result += "=" * 60 + "\n\n"
        
        # User Information
        user_info = context.get('user_info', {})
        result += f"👤 User Information:\n"
        result += f"   Name: {user_info.get('name', 'Unknown')}\n"
        if user_info.get('nickname'):
            result += f"   Nickname: {user_info.get('nickname')}\n"
        if user_info.get('preferred_address'):
            result += f"   Preferred Address: {user_info.get('preferred_address')}\n"
        
        # Persona Information
        persona_info = context.get('persona_info', {})
        result += f"\n🎭 Persona Information:\n"
        result += f"   Name: {persona_info.get('name', persona)}\n"
        if persona_info.get('nickname'):
            result += f"   Nickname: {persona_info.get('nickname')}\n"
        if persona_info.get('preferred_address'):
            result += f"   How to be called: {persona_info.get('preferred_address')}\n"
        
        # Current States
        result += f"\n🎨 Current States:\n"
        result += f"   Emotion: {context.get('current_emotion', 'neutral')}\n"
        result += f"   Physical: {context.get('physical_state', 'normal')}\n"
        result += f"   Mental: {context.get('mental_state', 'calm')}\n"
        result += f"   Environment: {context.get('environment', 'unknown')}\n"
        result += f"   Relationship: {context.get('relationship_status', 'normal')}\n"
        
        # ===== PART 2: Time Since Last Conversation =====
        last_time_str = context.get("last_conversation_time")
        current_time = get_current_time()
        
        result += f"\n⏰ Time Information:\n"
        if last_time_str:
            time_diff = calculate_time_diff(last_time_str)
            result += f"   Last Conversation: {time_diff['formatted_string']}前\n"
            result += f"   Previous: {last_time_str[:19]}\n"
            result += f"   Current: {current_time.isoformat()[:19]}\n"
        else:
            result += f"   Status: First conversation! 🆕\n"
            result += f"   Current: {current_time.isoformat()[:19]}\n"
        
        # Update last conversation time
        context["last_conversation_time"] = current_time.isoformat()
        save_persona_context(context, persona)
        
        # ===== PART 3: Memory Statistics =====
        db_path = get_db_path()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Total count
            cursor.execute('SELECT COUNT(*) FROM memories')
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                result += f"\n📊 Memory Statistics:\n"
                result += f"   No memories yet\n"
            else:
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
                
                # Build memory statistics
                result += f"\n📊 Memory Statistics:\n"
                result += f"   Total Memories: {total_count}\n"
                result += f"   Total Characters: {total_chars:,}\n"
                result += f"   Date Range: {min_date[:10]} ~ {max_date[:10]}\n"
                
                result += f"\n⭐ Importance Distribution:\n"
                result += f"   Average: {avg_importance:.2f}\n"
                result += f"   Range: {min_importance:.2f} ~ {max_importance:.2f}\n"
                result += f"   High (≥0.7): {high_importance_count}\n"
                result += f"   Medium (0.4~0.7): {medium_importance_count}\n"
                result += f"   Low (<0.4): {low_importance_count}\n"
                
                if emotion_counts:
                    result += f"\n💭 Emotion Distribution:\n"
                    for emotion, count in emotion_counts[:5]:  # Top 5 emotions
                        result += f"   {emotion}: {count}\n"
                
                if tag_counts:
                    result += f"\n🏷️  Tag Distribution:\n"
                    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
                    for tag, count in sorted_tags[:5]:  # Top 5 tags
                        result += f"   {tag}: {count}\n"
                
                result += f"\n🕐 Recent {len(recent)} Memories:\n"
                for i, (key, content, created_at, importance, emotion) in enumerate(recent, 1):
                    preview = content[:50] + "..." if len(content) > 50 else content
                    created_date = created_at[:10]
                    time_diff_mem = calculate_time_diff(created_at)
                    importance_str = f"{importance:.2f}" if importance is not None else "0.50"
                    emotion_str = emotion if emotion else "neutral"
                    result += f"{i}. [{key}] {preview}\n"
                    result += f"   {created_date} ({time_diff_mem['formatted_string']}前) | ⭐{importance_str} | 💭{emotion_str}\n"
        
        result += "\n" + "=" * 60 + "\n"
        result += "💡 Tip: Use search_memory_rag(query) for detailed semantic search\n"
        
        log_operation("get_session_context", metadata={"total_count": total_count, "persona": persona})
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to get session context: {e}")
        log_operation("get_session_context", success=False, error=str(e))
        return f"Failed to get session context: {str(e)}"
