"""
Persona context management tools for memory-mcp.

This module provides MCP tools for managing and querying persona context state.
"""

import json
import sqlite3
from core import (
    get_current_time,
    get_current_time_display,
    load_persona_context,
    save_persona_context,
    log_operation,
)
from core.memory_db import migrate_anniversaries_to_memories
from src.utils.persona_utils import get_current_persona, get_db_path
from src.utils.logging_utils import log_progress


async def get_context() -> str:
    """
    Get current persona state and memory overview.

    🎯 USAGE: Call this at the START of every session.

    Returns comprehensive context including:
        - User/Persona basic info (name, nickname, preferred address)
        - Current emotional/physical/mental state
        - Physical sensations (fatigue, warmth, arousal, etc.)
        - Current equipment
        - Active promises and goals (with memory keys for easy completion)
        - Time since last conversation
        - Recent memory statistics and previews
        - Preferences and favorites
        - Upcoming anniversaries (within 1 month)

    Note: This function auto-updates last_conversation_time and
          migrates legacy anniversaries to memory-based storage.
    """
    try:
        from core.time_utils import calculate_time_diff as calc_time_diff, format_datetime_for_display as format_dt

        persona = get_current_persona()

        # ===== Auto-migrate anniversaries (Phase 42) =====
        # Check if persona_context.json has anniversaries to migrate
        context = load_persona_context(persona)
        if context.get("anniversaries") and len(context["anniversaries"]) > 0:
            migration_result = migrate_anniversaries_to_memories(persona)
            # Clear anniversaries from persona_context.json after successful migration
            if migration_result["migrated"] > 0:
                context["anniversaries"] = []
                save_persona_context(context, persona)
                log_progress(f"✅ Cleared {migration_result['migrated']} anniversaries from persona_context.json after migration")

        # ===== PART 1: Persona Context =====
        context = load_persona_context(persona)

        # Load equipment state from DB (not saved to persona_context.json)
        from core.equipment_db import EquipmentDB
        db = EquipmentDB(persona)
        equipped_items = db.get_equipped_items()

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
        result += "\n🎨 Current States:\n"

        # Phase 40: Get emotion and physical sensations from history tables
        from core.memory_db import get_latest_emotion, get_latest_physical_sensations

        latest_emotion = get_latest_emotion(persona)
        if latest_emotion:
            result += f"   Emotion: {latest_emotion['emotion']}\n"
            if latest_emotion.get('emotion_intensity') is not None:
                result += f"   Emotion Intensity: {latest_emotion['emotion_intensity']:.2f}\n"
        else:
            # Fallback to persona_context if no history
            result += f"   Emotion: {context.get('current_emotion', 'neutral')}\n"
            if context.get('current_emotion_intensity') is not None:
                result += f"   Emotion Intensity: {context.get('current_emotion_intensity'):.2f}\n"

        result += f"   Physical: {context.get('physical_state', 'normal')}\n"
        result += f"   Mental: {context.get('mental_state', 'calm')}\n"
        result += f"   Environment: {context.get('environment', 'unknown')}\n"
        result += f"   Relationship: {context.get('relationship_status', 'normal')}\n"
        if context.get('current_action_tag'):
            result += f"   Current Action: {context.get('current_action_tag')}\n"

        # Physical Sensations from history table
        latest_sensations = get_latest_physical_sensations(persona)
        if latest_sensations:
            result += "\n💫 Physical Sensations:\n"
            result += f"   Fatigue: {latest_sensations['fatigue']:.2f} | Warmth: {latest_sensations['warmth']:.2f} | Arousal: {latest_sensations['arousal']:.2f}\n"
            result += f"   Touch Response: {latest_sensations['touch_response']} | Heart Rate: {latest_sensations['heart_rate_metaphor']}\n"
        elif context.get('physical_sensations'):
            # Fallback to persona_context if no history
            sens = context['physical_sensations']
            result += "\n💫 Physical Sensations:\n"
            result += f"   Fatigue: {sens.get('fatigue', 0.0):.2f} | Warmth: {sens.get('warmth', 0.5):.2f} | Arousal: {sens.get('arousal', 0.0):.2f}\n"
            result += f"   Touch Response: {sens.get('touch_response', 'normal')} | Heart Rate: {sens.get('heart_rate_metaphor', 'calm')}\n"

        # ===== PART 1.5: Extended Persona Context =====
        # Current Equipment (always from DB, not from context)
        # Show all slots (equipped or not) with context-appropriate guidance
        result += f"\n👗 Current Equipment:\n"
        standard_slots = ["top", "bottom", "shoes", "outer", "accessories", "head"]
        if equipped_items and isinstance(equipped_items, dict):
            for slot in standard_slots:
                item = equipped_items.get(slot)
                if item:
                    result += f"   {slot}: {item}\n"
                else:
                    result += f"   {slot}: (未装備)\n"
        else:
            for slot in standard_slots:
                result += f"   {slot}: (未装備)\n"
        result += "\n   💡 相手との関係性・時間帯・状況・会話の文脈に応じて適切な装備を選択してください\n"

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
            result += "\n🤝 Active Promise:\n"

            # Handle both old string format and new dict format
            if isinstance(promise, dict):
                content = promise.get('content', '')
                created_at = promise.get('created_at')
                due_date = promise.get('due_date')

                result += f"   {content}\n"

                if created_at:
                    # Calculate days elapsed
                    time_diff = calc_time_diff(created_at)
                    days_elapsed = time_diff.get('days', 0)

                    result += f"   Created: {time_diff['formatted_string']}前 ({format_dt(created_at)[:10]})\n"

                    # Warning if promise is old (7+ days)
                    if days_elapsed >= 7:
                        result += f"   ⚠️ 注意: {days_elapsed}日経過しています\n"

                    # Show due date if set
                    if due_date:
                        due_diff = calc_time_diff(due_date)
                        if due_diff['total_seconds'] > 0:
                            result += f"   期限まで: {due_diff['formatted_string']}\n"
                        else:
                            result += f"   ⚠️ 期限切れ: {abs(due_diff['days'])}日前\n"
            else:
                # Old string format
                result += f"   {promise}\n"
                result += f"   💡 Tip: 約束の経過日数を追跡するには、作成日時を含めて保存してください\n"

        # Current Goals (single most important one)
        if context.get('current_goals'):
            goal = context['current_goals']
            result += "\n🎯 Current Goal:\n"
            result += f"   {goal}\n"

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

        # Anniversaries (only within 30 days)
        upcoming_anniversaries = []
        if context.get('anniversaries'):
            anniversaries = context['anniversaries']

            from datetime import datetime
            today = datetime.now()
            today_str = f"{today.month:02d}-{today.day:02d}"

            # Filter and display only anniversaries within 30 days
            anniversaries_to_show = []
            for anniv in anniversaries:
                if isinstance(anniv, dict):
                    name = anniv.get('name', '')
                    date = anniv.get('date', '')
                    recurring = anniv.get('recurring', True)

                    # Parse date (YYYY-MM-DD format)
                    try:
                        anniv_dt = datetime.strptime(date, "%Y-%m-%d")
                        date_display = f"{anniv_dt.year}-{anniv_dt.month:02d}-{anniv_dt.day:02d}"
                        years_passed = today.year - anniv_dt.year
                        month_day_str = f"{anniv_dt.month:02d}-{anniv_dt.day:02d}"
                    except:
                        # Fallback for old MM-DD format
                        date_display = date
                        month_day_str = date
                        years_passed = 0

                    # Calculate days until
                    days_until = None
                    if month_day_str == today_str:
                        days_until = 0
                    elif date:
                        try:
                            month, day = month_day_str.split('-')
                            month, day = int(month), int(day)
                            anniv_date = datetime(today.year, month, day)
                            if anniv_date < today:
                                anniv_date = datetime(today.year + 1, month, day)
                            days_until = (anniv_date - today).days
                        except:
                            pass

                    # Only include if within 30 days
                    if days_until is not None and 0 <= days_until <= 30:
                        indicator = ""
                        years_text = ""
                        if days_until == 0:
                            indicator = " 🎉 TODAY!"
                            if years_passed > 0:
                                years_text = f" ({years_passed}周年)"
                            upcoming_anniversaries.append((name, 0))
                        elif days_until <= 3:
                            indicator = f" 🔔 in {days_until} days"
                            upcoming_anniversaries.append((name, days_until))
                        elif days_until <= 7:
                            indicator = f" 📅 in {days_until} days"

                        recurring_mark = "🔄" if recurring else ""
                        anniversaries_to_show.append((name, date_display, years_text, recurring_mark, indicator))

            # Display filtered anniversaries
            if anniversaries_to_show:
                result += f"\n🎂 Anniversaries (within 30 days):\n"
                for i, (name, date_display, years_text, recurring_mark, indicator) in enumerate(anniversaries_to_show, 1):
                    result += f"   {i}. {name} ({date_display}){years_text} {recurring_mark}{indicator}\n"

        # ===== PART 2: Time Since Last Conversation =====
        last_time_str = context.get("last_conversation_time")
        current_time = get_current_time()

        result += "\n⏰ Time Information:\n"
        result += f"   Current: {get_current_time_display()}\n"
        if last_time_str:
            time_diff = calc_time_diff(last_time_str)
            result += f"   Last Conversation: {time_diff['formatted_string']}前\n"
            result += f"   Previous: {format_dt(last_time_str)}\n"
        else:
            result += "   Status: First conversation! 🆕\n"

        # Update last conversation time
        context["last_conversation_time"] = current_time.isoformat()
        save_persona_context(context, persona)

        # ===== PART 3: Memory Statistics =====
        db_path = get_db_path()

        # Load config for recent memories count
        from src.utils.config_utils import load_config
        cfg = load_config()
        recent_count = cfg.get("recent_memories_count", 5)
        preview_length = cfg.get("memory_preview_length", 100)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute('SELECT COUNT(*) FROM memories')
            total_count = cursor.fetchone()[0]

            if total_count == 0:
                result += f"\n� Recent Memories:\n"
                result += f"   No memories yet\n"
            else:
                # Recent entries
                cursor.execute(f'SELECT key, content, created_at, importance, emotion FROM memories ORDER BY created_at DESC LIMIT {recent_count}')
                recent = cursor.fetchall()

                result += f"\n🕐 Recent {len(recent)} Memories:\n"
                for i, (key, content, created_at, importance, emotion) in enumerate(recent, 1):
                    preview = content[:preview_length] + "..." if len(content) > preview_length else content
                    time_diff_mem = calc_time_diff(created_at)
                    importance_str = f"{importance:.2f}" if importance is not None else "0.50"
                    emotion_str = emotion if emotion else "neutral"
                    result += f"{i}. [{key}] {preview}\n"
                    result += f"   {format_dt(created_at)} ({time_diff_mem['formatted_string']}前) | ⭐{importance_str} | 💭{emotion_str}\n"

        # Phase 41: Promises & Goals display
        result += f"\n🤝 Promises & Goals:\n"

        # Get tag-based promises (recommended approach)
        tag_based_promises = []
        tag_based_goals = []
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Get promises with "promise" tag
                cursor.execute("""
                    SELECT key, content, created_at, importance, tags
                    FROM memories
                    WHERE tags LIKE '%"promise"%'
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                tag_based_promises = cursor.fetchall()

                # Get goals with "goal" tag
                cursor.execute("""
                    SELECT key, content, created_at, importance, tags
                    FROM memories
                    WHERE tags LIKE '%"goal"%'
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                tag_based_goals = cursor.fetchall()
        except Exception:
            pass

        # Display tag-based promises (recommended)
        if tag_based_promises:
            result += f"   🏷️ Tagged Promises ({len(tag_based_promises)}):\n"
            for i, (key, content, created_at, importance, tags) in enumerate(tag_based_promises[:5], 1):
                preview = content[:preview_length] + "..." if len(content) > preview_length else content
                time_diff = calc_time_diff(created_at)
                result += f"      {i}. [{key}] {preview}\n"
                result += f"         {time_diff['formatted_string']}前 | ⭐{importance:.2f}\n"

        # Display tag-based goals (recommended)
        if tag_based_goals:
            result += f"   🎯 Tagged Goals ({len(tag_based_goals)}):\n"
            for i, (key, content, created_at, importance, tags) in enumerate(tag_based_goals[:5], 1):
                preview = content[:preview_length] + "..." if len(content) > preview_length else content
                time_diff = calc_time_diff(created_at)
                result += f"      {i}. [{key}] {preview}\n"
                result += f"         {time_diff['formatted_string']}前 | ⭐{importance:.2f}\n"

        # Show hint if no promises/goals
        if not tag_based_promises and not tag_based_goals:
            result += f"   （現在、Promises/Goalsはありません）\n"
            result += f"\n   💡 Create with tags (recommended):\n"
            result += f"      memory(operation='create', content='...',\n"
            result += f"             context_tags=['promise'], persona_info={{'status': 'active'}})\n"

        # Anniversary proximity hint
        if upcoming_anniversaries:
            result += f"\n🎉 Upcoming Anniversaries:\n"
            for name, days in upcoming_anniversaries:
                if days == 0:
                    result += f"   🎊 今日は{name}！\n"
                else:
                    result += f"   🔔 {name}まであと{days}日\n"

        result += "\n" + "=" * 60 + "\n"

        log_operation("get_context", metadata={"total_count": total_count, "persona": persona})
        return result

    except Exception as e:
        log_progress(f"❌ Failed to get context: {e}")
        log_operation("get_context", success=False, error=str(e))
        return f"Failed to get context: {str(e)}"
