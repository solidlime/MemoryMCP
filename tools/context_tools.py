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
from src.utils.persona_utils import get_current_persona, get_db_path
from src.utils.logging_utils import log_progress


async def get_context() -> str:
    """
    Get current conversation state including user/persona info, time since last conversation, and memory stats.
    Auto-updates last conversation timestamp.
    """
    try:
        from core.time_utils import calculate_time_diff as calc_time_diff, format_datetime_for_display as format_dt
        
        persona = get_current_persona()
        
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
        
        # Recent Emotion Changes from emotion_history table
        from core.memory_db import get_emotion_timeline
        emotion_timeline = get_emotion_timeline(days=7, persona=persona)
        if emotion_timeline and len(emotion_timeline) > 0:
            result += "\n📊 Recent Emotion Changes (last 5):\n"
            for i, entry in enumerate(reversed(emotion_timeline[-5:]), 1):
                emo = entry.get('emotion', 'neutral')
                intensity = entry.get('emotion_intensity', 0.5)
                timestamp = entry.get('timestamp', '')
                if timestamp:
                    time_diff = calc_time_diff(timestamp)
                    result += f"   {i}. {emo} ({intensity:.2f}) - {time_diff['formatted_string']}前\n"
                else:
                    result += f"   {i}. {emo} ({intensity:.2f})\n"
        elif context.get('emotion_history'):
            # Fallback to persona_context if no history table
            history = context['emotion_history']
            if len(history) > 0:
                result += "\n📊 Recent Emotion Changes (last 5):\n"
                for i, entry in enumerate(reversed(history[-5:]), 1):
                    emo = entry.get('emotion_type', 'neutral')
                    intensity = entry.get('intensity', 0.5)
                    timestamp = entry.get('timestamp', '')
                    if timestamp:
                        time_diff = calc_time_diff(timestamp)
                        result += f"   {i}. {emo} ({intensity:.2f}) - {time_diff['formatted_string']}前\n"
                    else:
                        result += f"   {i}. {emo} ({intensity:.2f})\n"
        
        # ===== PART 1.5: Extended Persona Context =====
        # Current Equipment (always from DB, not from context)
        result += f"\n👗 Current Equipment:\n"
        if equipped_items:
            equipment = equipped_items
            if isinstance(equipment, dict):
                for equip_type, item in equipment.items():
                    if isinstance(item, list):
                        result += f"   {equip_type}: {', '.join(item)}\n"
                    else:
                        result += f"   {equip_type}: {item}\n"
            else:
                result += f"   {equipment}\n"
        else:
            result += "   (装備なし)\n"
            result += "   💡 ヒント: 状況に応じて衣装を検討してください\n"
        
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
        
        # Anniversaries
        upcoming_anniversaries = []  # Track upcoming anniversaries for later hint
        if context.get('anniversaries'):
            anniversaries = context['anniversaries']
            result += f"\n🎂 Anniversaries:\n"
            
            from datetime import datetime
            today = datetime.now()
            today_str = f"{today.month:02d}-{today.day:02d}"
            
            # Display anniversaries with proximity indicators
            for i, anniv in enumerate(anniversaries, 1):
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
                    
                    # Check if today or upcoming
                    indicator = ""
                    years_text = ""
                    if month_day_str == today_str:
                        indicator = " 🎉 TODAY!"
                        if years_passed > 0:
                            years_text = f" ({years_passed}周年)"
                        upcoming_anniversaries.append((name, 0))
                    elif date:
                        # Calculate days until (simple month-day comparison)
                        try:
                            month, day = month_day_str.split('-')
                            month, day = int(month), int(day)
                            anniv_date = datetime(today.year, month, day)
                            if anniv_date < today:
                                anniv_date = datetime(today.year + 1, month, day)
                            days_until = (anniv_date - today).days
                            if 0 < days_until <= 3:
                                indicator = f" 🔔 in {days_until} days"
                                upcoming_anniversaries.append((name, days_until))
                            elif 0 < days_until <= 7:
                                indicator = f" 📅 in {days_until} days"
                        except:
                            pass
                    
                    recurring_mark = "🔄" if recurring else ""
                    result += f"   {i}. {name} ({date_display}){years_text} {recurring_mark}{indicator}\n"
                else:
                    result += f"   {i}. {anniv}\n"
        
        # ===== PART 2: Time Since Last Conversation =====
        last_time_str = context.get("last_conversation_time")
        current_time = get_current_time()
        
        result += "\n⏰ Time Information:\n"
        result += f"   Current: {get_current_time_display()}\n"
        if last_time_str:
            time_diff = calc_time_diff(last_time_str)
            result += f"   Last Conversation: {time_diff['formatted_string']}前\n"
            result += f"   Previous: {format_dt(last_time_str)}\n"
            
            # Calculate reunion context
            total_hours = time_diff.get('total_seconds', 0) / 3600
            
            # Reunion Intensity calculation (0.0-1.0)
            # 0-2h: 0.0-0.2, 2-8h: 0.2-0.4, 8-16h: 0.4-0.6, 16-36h: 0.6-0.8, 36h+: 0.8-1.0
            if total_hours <= 2:
                reunion_intensity = min(total_hours / 10, 0.2)
            elif total_hours <= 8:
                reunion_intensity = 0.2 + ((total_hours - 2) / 30)
            elif total_hours <= 16:
                reunion_intensity = 0.4 + ((total_hours - 8) / 40)
            elif total_hours <= 36:
                reunion_intensity = 0.6 + ((total_hours - 16) / 100)
            else:
                reunion_intensity = min(0.8 + ((total_hours - 36) / 200), 1.0)
            
            # Separation category
            if total_hours < 2:
                separation_category = "短時間の不在"
            elif total_hours < 8:
                separation_category = "数時間の不在"
            elif total_hours < 16:
                separation_category = "半日の不在"
            elif total_hours < 36:
                separation_category = "1日程度の不在"
            elif total_hours < 72:
                separation_category = "数日の不在"
            else:
                separation_category = "長期の不在"
            
            # Display reunion context
            stars = "★" * min(int(reunion_intensity * 5) + 1, 5)
            stars += "☆" * (5 - len(stars))
            
            result += f"\n💫 Reunion Context:\n"
            result += f"   Reunion Intensity: {reunion_intensity:.2f} {stars}\n"
            result += f"   Separation: {separation_category}\n"
            
            # === Concern Level & Triggers (conditional) ===
            concerns = []
            concern_level = 0.0
            
            # Check for broken promises
            active_promise = context.get('active_promises')
            if active_promise and isinstance(active_promise, dict):
                due_date = active_promise.get('due_date')
                if due_date:
                    due_diff = calc_time_diff(due_date)
                    if due_diff['total_seconds'] < 0:  # Past due
                        days_overdue = abs(due_diff.get('days', 0))
                        if days_overdue > 0:
                            concerns.append(f"約束期限を{days_overdue}日超過")
                            concern_level += min(0.3 + (days_overdue * 0.1), 0.8)
            
            # Check for very long absence (3+ days)
            if total_hours >= 72:
                days_absent = int(total_hours / 24)
                concerns.append(f"{days_absent}日間連絡なし")
                concern_level += min(0.4 + ((days_absent - 3) * 0.1), 0.6)
            
            # Check for emotional context from last conversation
            if latest_emotion:
                last_emotion = latest_emotion.get('emotion', '')
                last_intensity = latest_emotion.get('emotion_intensity', 0.5)
                
                # High intensity negative emotions that ended abruptly
                if last_emotion in ['sadness', 'fear', 'anxiety'] and last_intensity > 0.7:
                    concerns.append(f"前回の会話が未解決な感情で終了 ({last_emotion})")
                    concern_level += 0.3
            
            # Display concerns if concern_level > 0.3
            if concern_level > 0.3 and concerns:
                concern_stars = "★" * min(int(concern_level * 5) + 1, 5)
                concern_stars += "☆" * (5 - len(concern_stars))
                
                result += f"\n⚠️ Emotional Alerts:\n"
                result += f"   Concern Level: {concern_level:.2f} {concern_stars}\n"
                result += f"   Triggers:\n"
                for concern in concerns:
                    result += f"     - {concern}\n"
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
        
        # Check for routine suggestions (lightweight)
        routine_suggestions_available = False
        try:
            current_hour = current_time.hour
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Check if there are recurring patterns at this time (±1 hour)
                cursor.execute('''
                    SELECT COUNT(*) FROM memories
                    WHERE created_at > datetime('now', '-30 days')
                    AND CAST(strftime('%H', created_at) AS INTEGER) BETWEEN ? AND ?
                    AND emotion IN ('joy', 'love', 'peaceful', 'excitement')
                ''', (current_hour - 1, current_hour + 1))
                count = cursor.fetchone()[0]
                if count >= 5:
                    routine_suggestions_available = True
        except Exception:
            pass  # Silently fail, not critical
        
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
                
                result += f"\n🕐 Recent {len(recent)} Memories:\n"
                for i, (key, content, created_at, importance, emotion) in enumerate(recent, 1):
                    preview = content[:50] + "..." if len(content) > 50 else content
                    time_diff_mem = calc_time_diff(created_at)
                    importance_str = f"{importance:.2f}" if importance is not None else "0.50"
                    emotion_str = emotion if emotion else "neutral"
                    result += f"{i}. [{key}] {preview}\n"
                    result += f"   {format_dt(created_at)} ({time_diff_mem['formatted_string']}前) | ⭐{importance_str} | 💭{emotion_str}\n"
        
        # Add routine suggestion hint if available
        if routine_suggestions_available:
            result += f"\n💫 Routine Check Available:\n"
            result += f"   check_routines()で「いつも」のパターンを確認できます\n"
        
        # Check for pending tasks/plans
        pending_tasks_available = False
        try:
            task_tags = ["plan", "TODO", "todo", "task", "タスク", "予定", "実装予定", "milestone"]
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Check for recent task/plan memories
                for tag in task_tags:
                    cursor.execute('''
                        SELECT COUNT(*) FROM memories
                        WHERE tags LIKE ?
                        AND created_at > datetime('now', '-60 days')
                    ''', (f'%"{tag}"%',))
                    count = cursor.fetchone()[0]
                    if count > 0:
                        pending_tasks_available = True
                        break
                
                # Also check content for task keywords
                if not pending_tasks_available:
                    cursor.execute('''
                        SELECT COUNT(*) FROM memories
                        WHERE (content LIKE '%実装予定%' OR content LIKE '%タスク%' OR content LIKE '%TODO%' OR content LIKE '%優先度%')
                        AND created_at > datetime('now', '-60 days')
                    ''')
                    count = cursor.fetchone()[0]
                    if count > 0:
                        pending_tasks_available = True
        except Exception:
            pass  # Silently fail, not critical
        
        if pending_tasks_available:
            result += f"\n📋 Pending Tasks/Plans Found:\n"
            result += f"   memory(operation='search', mode='task')でタスク一覧表示\n"
            result += f"   memory(operation='search', mode='plan')で予定・計画一覧表示\n"
        
        # Phase 41: Promises & Goals hint
        result += f"\n🤝 Promises & Goals:\n"
        result += f"   memory(operation='promise')で約束を確認\n"
        result += f"   memory(operation='goal')で目標を確認\n"
        
        # Anniversary proximity hint
        if upcoming_anniversaries:
            result += f"\n🎉 Upcoming Anniversaries:\n"
            for name, days in upcoming_anniversaries:
                if days == 0:
                    result += f"   🎊 今日は{name}！\n"
                else:
                    result += f"   🔔 {name}まであと{days}日\n"
        
        result += "\n" + "=" * 60 + "\n"
        result += "💡 Tip: Use read_memory(query) for semantic search\n"
        
        log_operation("get_context", metadata={"total_count": total_count, "persona": persona})
        return result
        
    except Exception as e:
        log_progress(f"❌ Failed to get context: {e}")
        log_operation("get_context", success=False, error=str(e))
        return f"Failed to get context: {str(e)}"
