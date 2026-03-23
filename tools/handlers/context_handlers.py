"""Context operation handlers (update_context only)."""

from typing import Optional, Dict
from datetime import datetime
from zoneinfo import ZoneInfo

from core.persona_context import load_persona_context, save_persona_context
from core.user_state_db import update_user_state_bulk, USER_STATE_KEYS
from src.utils.persona_utils import get_current_persona
from src.utils.config_utils import load_config


async def handle_update_context(
    persona_info: Optional[Dict] = None,
    user_info: Optional[Dict] = None,
    emotion_type: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
) -> str:
    """Batch update multiple context fields."""
    persona = get_current_persona()
    context = load_persona_context(persona)
    updated_fields = []

    cfg = load_config()
    now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))).isoformat()

    # Update user_info fields — bi-temporal history + persona_context.json (for fast reads)
    if user_info:
        if 'user_info' not in context:
            context['user_info'] = {}

        fields_to_track = {}
        for key in USER_STATE_KEYS:
            if key in user_info and user_info[key] is not None:
                context['user_info'][key] = user_info[key]
                updated_fields.append(f"user_{key}")
                fields_to_track[key] = str(user_info[key])

        # Persist bi-temporal history (non-blocking best-effort)
        if fields_to_track:
            try:
                update_user_state_bulk(persona, fields_to_track)
            except Exception:
                pass  # history is best-effort; context.json update already done

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

        # Update persona self-info (nickname / preferred_address)
        if 'nickname' in persona_info or 'preferred_address' in persona_info:
            if 'persona_info' not in context:
                context['persona_info'] = {}
            for key in ('nickname', 'preferred_address'):
                if key in persona_info and persona_info[key] is not None:
                    context['persona_info'][key] = persona_info[key]
                    updated_fields.append(f'persona_{key}')

    # Update emotion (write to emotion_history table + persona_context.json)
    if emotion_type:
        from core.memory_db import save_emotion_history
        intensity = emotion_intensity if emotion_intensity is not None else 0.5
        save_emotion_history(None, emotion_type, intensity, now, persona)
        context['current_emotion'] = emotion_type
        context['current_emotion_intensity'] = intensity
        updated_fields.append('emotion')

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
    Handle context operations (update_context only).

    Note: promise/goal operations now use tag-based memory approach.
    Use memory(operation='create', context_tags=['promise']) instead.

    Args:
        operation: Operation type (update_context)
        persona_info: Additional persona information
        user_info: User information to update

    Returns:
        Operation result string
    """
    operation = operation.lower()

    if operation in ["promise", "goal"]:
        raise ValueError(f"Operation '{operation}' is no longer supported. "
                        f"Use tag-based approach: memory(operation='create', content='...', "
                        f"context_tags=['{operation}'], persona_info={{...}})")
    elif operation == "update_context":
        if not persona_info and not user_info and not emotion_type:
            return "ℹ️ No context fields to update\n💡 Example: memory(operation='update_context', physical_state='relaxed', mental_state='calm')"
        return await handle_update_context(persona_info, user_info, emotion_type, emotion_intensity)

    # ── Named memory block operations (廃止済み) ─────────────────────────────
    elif operation in ("block_write", "block_read", "block_list", "block_delete"):
        raise ValueError(
            f"Operation '{operation}' は廃止されました。Memory Blocks 機能は削除されています。"
        )

    else:
        raise ValueError(
            f"Unknown context operation '{operation}'. "
            f"Valid: update_context"
        )
