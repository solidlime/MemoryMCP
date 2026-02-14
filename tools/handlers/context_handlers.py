"""Context operation handlers (promise, goal, favorites, etc.)."""

from typing import Optional, Dict
from datetime import datetime
from zoneinfo import ZoneInfo

from core.memory_db import (
    save_promise,
    get_promises,
    update_promise_status,
    save_goal,
    get_goals,
    update_goal_progress,
    get_emotion_history_from_db,
    save_emotion_history,
)
from core import calculate_time_diff
from core.persona_context import load_persona_context, save_persona_context
from src.utils.persona_utils import get_current_persona, get_db_path
from src.utils.config_utils import load_config
from src.utils.logging_utils import log_progress
from tools.helpers.routine_helpers import analyze_situation_context


async def handle_promise(query: Optional[str], content: Optional[str], importance: Optional[float]) -> str:
    """
    Manage promises (SQLite-based, multiple promises).

    Args:
        query: Action query (complete:ID, cancel:ID, list:status)
        content: Promise content (to add new)
        importance: Priority level

    Returns:
        Result string
    """
    # Parse query for actions
    if query:
        if query.startswith("complete:"):
            promise_id = int(query.split(":")[1])
            if update_promise_status(promise_id, "completed"):
                return f"✅ Promise #{promise_id} completed!"
            return f"❌ Failed to complete promise #{promise_id}"

        elif query.startswith("cancel:"):
            promise_id = int(query.split(":")[1])
            if update_promise_status(promise_id, "cancelled"):
                return f"✅ Promise #{promise_id} cancelled"
            return f"❌ Failed to cancel promise #{promise_id}"

        elif query.startswith("list:"):
            status = query.split(":")[1]
            promises = get_promises(status=status)
            if not promises:
                return f"📝 No {status} promises."

            result = f"📝 {status.capitalize()} Promises ({len(promises)}):\n"
            for p in promises:
                result += f"  #{p['id']}: {p['content']}"
                if p['due_date']:
                    result += f" (due: {p['due_date'][:10]})"
                result += f" [priority: {p['priority']}]\n"
            return result

    # Add new promise or list active
    if content:
        promise_id = save_promise(content, priority=importance or 0)
        return f"✅ Promise added: {content} (ID: {promise_id})"

    # List active promises
    promises = get_promises(status="active")
    if not promises:
        return "📝 No active promises."

    result = f"📝 Active Promises ({len(promises)}):\n"
    for p in promises:
        time_diff = calculate_time_diff(p['created_at'])
        result += f"  #{p['id']}: {p['content']}"
        if p['due_date']:
            result += f" (due: {p['due_date'][:10]})"
        result += f" - {time_diff['formatted_string']}前\n"
    return result


async def handle_goal(query: Optional[str], content: Optional[str]) -> str:
    """
    Manage goals (SQLite-based, multiple goals with progress).

    Args:
        query: Action query (progress:ID:percentage, list:status)
        content: Goal content (to add new)

    Returns:
        Result string
    """
    # Parse query for actions
    if query:
        if query.startswith("progress:"):
            parts = query.split(":")
            goal_id = int(parts[1])
            progress = int(parts[2])
            if update_goal_progress(goal_id, progress):
                if progress >= 100:
                    return f"✅ Goal #{goal_id} completed! (100%)"
                return f"✅ Goal #{goal_id} progress updated: {progress}%"
            return f"❌ Failed to update goal #{goal_id}"

        elif query.startswith("list:"):
            status = query.split(":")[1]
            goals = get_goals(status=status)
            if not goals:
                return f"🎯 No {status} goals."

            result = f"🎯 {status.capitalize()} Goals ({len(goals)}):\n"
            for g in goals:
                result += f"  #{g['id']}: {g['content']} [{g['progress']}%]"
                if g['target_date']:
                    result += f" (target: {g['target_date'][:10]})"
                result += "\n"
            return result

    # Add new goal or list active
    if content:
        goal_id = save_goal(content)
        return f"✅ Goal added: {content} (ID: {goal_id})"

    # List active goals
    goals = get_goals(status="active")
    if not goals:
        return "🎯 No active goals."

    result = f"🎯 Active Goals ({len(goals)}):\n"
    for g in goals:
        time_diff = calculate_time_diff(g['created_at'])
        result += f"  #{g['id']}: {g['content']} [{g['progress']}%]"
        if g['target_date']:
            result += f" (target: {g['target_date'][:10]})"
        result += f" - {time_diff['formatted_string']}前\n"
    return result


async def handle_favorite(content: Optional[str]) -> str:
    """Add item to favorites list."""
    if not content:
        return "❌ Error: 'content' is required for favorite operation"

    persona = get_current_persona()
    context = load_persona_context(persona)

    if "favorite_items" not in context:
        context["favorite_items"] = []

    if isinstance(context["favorite_items"], str):
        context["favorite_items"] = [context["favorite_items"]]

    if content not in context["favorite_items"]:
        context["favorite_items"].append(content)
        save_persona_context(context, persona)
        return f"✅ Added to favorites: {content}"
    else:
        return f"ℹ️ Already in favorites: {content}"


async def handle_preference(persona_info: Dict) -> str:
    """Update preferences (loves/dislikes)."""
    if not persona_info or not any(k in persona_info for k in ["loves", "dislikes", "preferences"]):
        return "❌ Error: No preferences to update. Use persona_info={'loves': [...], 'dislikes': [...]}"

    context = load_persona_context(get_current_persona())
    if "preferences" not in context:
        context["preferences"] = {}

    prefs = persona_info.get("preferences", persona_info)
    updated = []
    for key in ["loves", "dislikes"]:
        if key in prefs:
            context["preferences"][key] = prefs[key]
            updated.append(key)

    save_persona_context(context, get_current_persona())
    return f"✅ Preferences updated: {', '.join(updated)}"


async def handle_update_context(persona_info: Optional[Dict] = None, user_info: Optional[Dict] = None) -> str:
    """Batch update multiple context fields."""
    persona = get_current_persona()
    context = load_persona_context(persona)
    updated_fields = []

    cfg = load_config()
    now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))).isoformat()

    # Update user_info fields
    if user_info:
        if 'user_info' not in context:
            context['user_info'] = {}

        for key in ['name', 'nickname', 'preferred_address']:
            if key in user_info:
                context['user_info'][key] = user_info[key]
                updated_fields.append(f"user_{key}")

    # Update persona_info fields if provided
    if persona_info:
        # Update promise
        if "active_promises" in persona_info:
            promise = persona_info["active_promises"]
            if promise:
                if isinstance(promise, str):
                    context["active_promises"] = {"content": promise, "created_at": now}
                else:
                    context["active_promises"] = promise
                updated_fields.append("promise")
            else:
                if "active_promises" in context:
                    del context["active_promises"]
                updated_fields.append("promise (cleared)")

        # Update goal
        if "current_goals" in persona_info:
            goal = persona_info["current_goals"]
            if goal:
                context["current_goals"] = goal
                updated_fields.append("goal")
            else:
                if "current_goals" in context:
                    del context["current_goals"]
                updated_fields.append("goal (cleared)")

        # Update favorites
        if "favorite_items" in persona_info:
            context["favorite_items"] = persona_info["favorite_items"]
            updated_fields.append("favorites")

        # Update preferences
        if "preferences" in persona_info:
            context["preferences"] = persona_info["preferences"]
            updated_fields.append("preferences")

        # Update physical_state, mental_state, environment, relationship_status
        for field in ['physical_state', 'mental_state', 'environment', 'relationship_status']:
            if field in persona_info:
                context[field] = persona_info[field]
                updated_fields.append(field)

        # Update action_tag
        if 'action_tag' in persona_info:
            context['current_action_tag'] = persona_info['action_tag']
            updated_fields.append('action_tag')

        # Update physical_sensations
        if 'physical_sensations' in persona_info:
            if 'physical_sensations' not in context:
                context['physical_sensations'] = {}

            sensations = persona_info['physical_sensations']
            for key in ['arousal', 'heart_rate', 'fatigue', 'warmth', 'touch_response', 'heart_rate_metaphor']:
                if key in sensations:
                    # Map heart_rate to heart_rate_metaphor if needed
                    if key == 'heart_rate':
                        context['physical_sensations']['heart_rate_metaphor'] = sensations[key]
                    else:
                        context['physical_sensations'][key] = sensations[key]
            updated_fields.append('physical_sensations')

    if updated_fields:
        save_persona_context(context, persona)
        return f"✅ Context updated: {', '.join(updated_fields)}"
    else:
        return "ℹ️ No context fields to update\n💡 Example: memory(operation='update_context', physical_state='relaxed', mental_state='calm')"


async def handle_anniversary(content: Optional[str], persona_info: Optional[Dict]) -> str:
    """Manage anniversaries (add, remove, list)."""
    persona = get_current_persona()
    context = load_persona_context(persona)

    # Initialize anniversaries list
    if "anniversaries" not in context:
        context["anniversaries"] = []

    # Migrate old MM-DD format to YYYY-MM-DD
    migrated = False
    for ann in context["anniversaries"]:
        date_str = ann.get("date", "")
        if date_str and len(date_str) == 5 and date_str[2] == '-':
            ann["date"] = f"2025-{date_str}"
            migrated = True
    if migrated:
        save_persona_context(context, persona)
        log_progress("✅ Migrated anniversary dates to YYYY-MM-DD format")

    # List all anniversaries
    if not content and not persona_info:
        if not context["anniversaries"]:
            return "📅 No anniversaries registered."

        result = "📅 Registered Anniversaries:\n"
        current_year = datetime.now().year
        for i, ann in enumerate(context["anniversaries"], 1):
            name = ann.get("name", "Unknown")
            date = ann.get("date", "????-??-??")
            recurring = ann.get("recurring", True)
            recur_text = " (毎年)" if recurring else " (一度きり)"

            try:
                ann_date = datetime.strptime(date, "%Y-%m-%d")
                years = current_year - ann_date.year
                if years > 0:
                    result += f"{i}. {name}: {date} ({years}年目){recur_text}\n"
                else:
                    result += f"{i}. {name}: {date}{recur_text}\n"
            except:
                result += f"{i}. {name}: {date}{recur_text}\n"
        return result

    # Add anniversary
    if content and persona_info and "date" in persona_info:
        date_str = persona_info["date"]
        recurring = persona_info.get("recurring", True)

        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return f"❌ Error: Invalid date format. Use YYYY-MM-DD (e.g., 2025-11-10)"

        # Check if exists (update)
        for ann in context["anniversaries"]:
            if ann.get("name") == content:
                ann["date"] = date_str
                ann["recurring"] = recurring
                save_persona_context(context, persona)
                return f"✅ Anniversary updated: {content} ({date_str})"

        # Add new
        context["anniversaries"].append({
            "name": content,
            "date": date_str,
            "recurring": recurring
        })
        save_persona_context(context, persona)
        return f"✅ Anniversary added: {content} ({date_str})"

    # Remove anniversary
    if content and (not persona_info or "date" not in persona_info):
        for i, ann in enumerate(context["anniversaries"]):
            if ann.get("name") == content:
                context["anniversaries"].pop(i)
                save_persona_context(context, persona)
                return f"✅ Anniversary removed: {content}"
        return f"❌ Anniversary not found: {content}"

    return "❌ Error: Provide content (name) and persona_info={'date': 'YYYY-MM-DD'} to add, or just content to remove"


async def handle_sensation(persona_info: Optional[Dict]) -> str:
    """Update physical sensations."""
    context = load_persona_context(get_current_persona())
    if "physical_sensations" not in context:
        context["physical_sensations"] = {
            "fatigue": 0.0, "warmth": 0.5, "arousal": 0.0,
            "touch_response": "normal", "heart_rate_metaphor": "calm"
        }

    sens = context["physical_sensations"]
    if not persona_info:
        return (f"💫 Current Physical Sensations:\n"
               f"   Fatigue: {sens.get('fatigue', 0.0):.2f}\n"
               f"   Warmth: {sens.get('warmth', 0.5):.2f}\n"
               f"   Arousal: {sens.get('arousal', 0.0):.2f}\n"
               f"   Touch Response: {sens.get('touch_response', 'normal')}\n"
               f"   Heart Rate: {sens.get('heart_rate_metaphor', 'calm')}")

    # Update sensations
    updated = []
    for key in ["fatigue", "warmth", "arousal"]:
        if key in persona_info:
            sens[key] = max(0.0, min(1.0, float(persona_info[key])))
            updated.append(key)
    for key in ["touch_response", "heart_rate_metaphor"]:
        if key in persona_info:
            sens[key] = persona_info[key]
            updated.append(key)

    if updated:
        save_persona_context(context, get_current_persona())
        return f"✅ Physical sensations updated: {', '.join(updated)}"
    return "ℹ️ No sensations to update"


async def handle_emotion_flow(emotion_type: Optional[str], emotion_intensity: Optional[float]) -> str:
    """Record emotion change to history (SQLite only)."""
    if not emotion_type:
        # Display history
        history = get_emotion_history_from_db(limit=10)
        if not history:
            return "📊 No emotion history yet."

        result = "📊 Recent Emotion Changes (last 10):\n"
        for i, entry in enumerate(history, 1):
            emo = entry['emotion']
            intensity = entry['emotion_intensity']
            timestamp = entry['timestamp']
            time_diff = calculate_time_diff(timestamp)
            result += f"{i}. {emo} ({intensity:.2f}) - {time_diff['formatted_string']}前\n"
        return result

    # Save to database
    intensity = emotion_intensity if emotion_intensity is not None else 0.5
    save_emotion_history(emotion=emotion_type, emotion_intensity=intensity, memory_key=None)
    return f"✅ Emotion recorded: {emotion_type} ({intensity:.2f})"


async def handle_situation_context() -> str:
    """Analyze current situation and provide context."""
    persona = get_current_persona()
    context = load_persona_context(persona)
    cfg = load_config()
    now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo")))
    db_path = get_db_path()

    return await analyze_situation_context(persona, context, now, db_path)


async def handle_context_operation(
    operation: str,
    query: Optional[str] = None,
    content: Optional[str] = None,
    emotion_type: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
    persona_info: Optional[Dict] = None,
    user_info: Optional[Dict] = None,
    importance: Optional[float] = None
) -> str:
    """
    Handle context operations.

    Args:
        operation: Operation type (promise, goal, favorite, preference, update_context,
                  anniversary, sensation, emotion_flow, situation_context)
        query: Query string for specific operations
        content: Content for the operation
        emotion_type: Emotion type
        emotion_intensity: Emotion intensity
        persona_info: Additional persona information
        user_info: User information to update
        importance: Importance/priority level

    Returns:
        Operation result string
    """
    operation = operation.lower()

    if operation == "promise":
        return await handle_promise(query, content, importance)
    elif operation == "goal":
        return await handle_goal(query, content)
    elif operation == "favorite":
        return await handle_favorite(content)
    elif operation == "preference":
        if not persona_info:
            return "❌ Error: persona_info required for preference operation"
        return await handle_preference(persona_info)
    elif operation == "update_context":
        if not persona_info and not user_info:
            return "ℹ️ No context fields to update\n💡 Example: memory(operation='update_context', physical_state='relaxed', mental_state='calm')"
        return await handle_update_context(persona_info, user_info)
    elif operation == "anniversary":
        return await handle_anniversary(content, persona_info)
    elif operation == "sensation":
        return await handle_sensation(persona_info)
    elif operation == "emotion_flow":
        return await handle_emotion_flow(emotion_type, emotion_intensity)
    elif operation == "situation_context":
        return await handle_situation_context()
    else:
        return f"❌ Error: Unknown context operation '{operation}'"
