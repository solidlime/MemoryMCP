"""
Persona context management tools for memory-mcp.

This module provides MCP tools for managing and querying persona context state.
"""

import json
import sqlite3
from core import (
    get_current_time,
    calculate_time_diff,
    format_datetime_for_display,
    get_current_time_display,
    load_persona_context,
    save_persona_context,
    log_operation,
)
from src.utils.persona_utils import get_current_persona, get_db_path


def _log_progress(message: str) -> None:
    """Internal logging function."""
    print(message, flush=True)


async def get_context() -> str:
    """
    Get current conversation state including user/persona info, time since last conversation, and memory stats.
    Auto-updates last conversation timestamp.
    """
    try:
        persona = get_current_persona()
        
        # ===== PART 1: Persona Context =====
        context = load_persona_context(persona)
        
        result = f"📋 Context (persona: {persona})\n"
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
        result += f"
🎨 Current States:
"
        result += f"   Emotion: {context.get('current_emotion', 'neutral')}
"
        if context.get('current_emotion_intensity') is not None:
            result += f"   Emotion Intensity: {context.get('current_emotion_intensity'):.2f}
"
        result += f"   Physical: {context.get('physical_state', 'normal')}
"
        result += f"   Mental: {context.get('mental_state', 'calm')}
"
        result += f"   Environment: {context.get('environment', 'unknown')}
"
        result += f"   Relationship: {context.get('relationship_status', 'normal')}
"
        if context.get('current_action_tag'):
            result += f"   Current Action: {context.get('current_action_tag')}
"
        
        # ===== PART 1.5: Extended Persona Context =====
        # Current Equipment
        if context.get('current_equipment'):
            equipment = context['current_equipment']
            result += f"\n👗 Current Equipment:\n"
            if isinstance(equipment, dict):
                for equip_type, item in equipment.items():
                    if isinstance(item, list):
                        result += f"   {equip_type}: {', '.join(item)}\n"
                    else:
                        result += f"   {equip_type}: {item}\n"
            else:
                result += f"   {equipment}\n"
        
        # Favorite Items
        if context.get('favorite_items'):
            items = context['favorite_items']
            result += f"\n💕 Favorite Items:\n"
            if isinstance(items, list):
                for item in items:
                    result += f"   - {item}\n"
            else:
                result += f"   {items}\n"
        
        # Active Promises (single most important one)
        if context.get('active_promises'):
            promise = context['active_promises']
            result += f"
🤝 Active Promise:
"
            result += f"   {promise}
"
        
        # Current Goals (single most important one)
        if context.get('current_goals'):
            goal = context['current_goals']
            result += f"
🎯 Current Goal:
"
            result += f"   {goal}
"
        
        # Preferences
        if context.get('preferences'):
            prefs = context['preferences']
            result += f"\n💖 Preferences:\n"
            if isinstance(prefs, dict):
                if prefs.get('loves'):
                    loves = prefs['loves']
                    if isinstance(loves, list):
                        result += f"   Loves: {', '.join(loves)}\n"
                    else:
                        result += f"   Loves: {loves}\n"
                if prefs.get('dislikes'):
                    dislikes = prefs['dislikes']
                    if isinstance(dislikes, list):
                        result += f"   Dislikes: {', '.join(dislikes)}\n"
                    else:
                        result += f"   Dislikes: {dislikes}\n"
            else:
                result += f"   {prefs}\n"
        
        # Special Moments (最近のもの、数件)
        if context.get('special_moments'):
            moments = context['special_moments']
            result += f"\n✨ Special Moments:\n"
            if isinstance(moments, list):
                for i, moment in enumerate(moments[-5:], 1):  # 最新5件まで
                    if isinstance(moment, dict):
                        content = moment.get('content', '')
                        date = moment.get('date', '')
                        emotion = moment.get('emotion', '')
                        result += f"   {i}. {content}"
                        if date:
                            result += f" ({date})"
                        if emotion:
                            result += f" 💭{emotion}"
                        result += "\n"
                    else:
                        result += f"   {i}. {moment}\n"
            else:
                result += f"   {moments}\n"
        
        # ===== PART 2: Time Since Last Conversation =====
        last_time_str = context.get("last_conversation_time")
        current_time = get_current_time()
        
        result += f"
⏰ Time Information:
"
        result += f"   Current: {get_current_time_display()}
"
        if last_time_str:
            time_diff = calculate_time_diff(last_time_str)
            result += f"   Last Conversation: {time_diff['formatted_string']}前
"
            result += f"   Previous: {format_datetime_for_display(last_time_str)}
"
        else:
            result += f"   Status: First conversation! 🆕
"
        
        # Update last conversation time
        context["last_conversation_time"] = current_time.isoformat()
        save_persona_context(context, persona)
        
        # ===== PART 3: Memory Statistics =====
        db_path = get_db_path()
        
        # Load config for recent memories count
        from src.utils.config_utils import load_config
        cfg = load_config()
        recent_count = cfg.get("recent_memories_count", 5)
        
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
                
                # Recent entries
                cursor.execute(f'SELECT key, content, created_at, importance, emotion FROM memories ORDER BY created_at DESC LIMIT {recent_count}')
                recent = cursor.fetchall()
                
                # Build memory statistics
                result += f"\n📊 Memory Statistics:\n"
                result += f"   Total Memories: {total_count}\n"
                result += f"   Total Characters: {total_chars:,}\n"
                result += f"   Date Range: {min_date[:10]} ~ {max_date[:10]}\n"
                
                result += f"
🕐 Recent {len(recent)} Memories:
"
                for i, (key, content, created_at, importance, emotion) in enumerate(recent, 1):
                    preview = content[:50] + "..." if len(content) > 50 else content
                    time_diff_mem = calculate_time_diff(created_at)
                    importance_str = f"{importance:.2f}" if importance is not None else "0.50"
                    emotion_str = emotion if emotion else "neutral"
                    result += f"{i}. [{key}] {preview}
"
                    result += f"   {format_datetime_for_display(created_at)} ({time_diff_mem['formatted_string']}前) | ⭐{importance_str} | 💭{emotion_str}
"
        
        result += "\n" + "=" * 60 + "\n"
        result += "💡 Tip: Use read_memory(query) for semantic search\n"
        
        log_operation("get_context", metadata={"total_count": total_count, "persona": persona})
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to get context: {e}")
        log_operation("get_context", success=False, error=str(e))
        return f"Failed to get context: {str(e)}"
