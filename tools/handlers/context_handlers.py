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
)
from core import calculate_time_diff
from core.persona_context import load_persona_context, save_persona_context
from src.utils.persona_utils import get_current_persona, get_db_path
from src.utils.config_utils import load_config
from src.utils.logging_utils import log_progress


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
        operation: Operation type (promise, goal, update_context)
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
    elif operation == "update_context":
        if not persona_info and not user_info:
            return "ℹ️ No context fields to update\n💡 Example: memory(operation='update_context', physical_state='relaxed', mental_state='calm')"
        return await handle_update_context(persona_info, user_info)
    else:
        valid_ops = ["promise", "goal", "update_context"]
        return f"❌ Error: Unknown context operation '{operation}'. Valid operations: {', '.join(valid_ops)}"
