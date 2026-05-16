from __future__ import annotations

import json
from typing import TYPE_CHECKING

from memory_mcp.domain.persona.entities import (
    BASIC_EMOTIONS,
    EmotionRecord,
    PersonaState,
    compute_dominant_emotion,
    default_emotions,
)
from memory_mcp.domain.shared.errors import DomainError, PersonaValidationError
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.domain.value_objects import normalize_emotion

if TYPE_CHECKING:
    from datetime import datetime

    from memory_mcp.domain.persona.repository import PersonaRepository


class PersonaService:
    """Domain service for persona state management."""

    def __init__(self, repo: PersonaRepository) -> None:
        self._repo = repo

    def get_context(self, persona: str) -> Result[PersonaState, DomainError]:
        """Get current persona state."""
        return self._repo.get_current_state(persona)

    def update_emotions(
        self,
        persona: str,
        emotions: dict[str, float],
        trigger_key: str | None = None,
        context: str | None = None,
    ) -> Result[None, DomainError]:
        """Update multi-dimensional emotions and record in history."""
        # Normalize: clamp to 0.0-1.0, fill missing with 0.0
        normalized: dict[str, float] = {}
        for e in BASIC_EMOTIONS:
            val = emotions.get(e, 0.0)
            normalized[e] = max(0.0, min(1.0, float(val)))

        # Compute dominant for backward compat
        dominant_name, dominant_intensity = compute_dominant_emotion(normalized)

        # Store multi-dimensional emotions as JSON
        emotions_json = json.dumps(normalized)
        result = self._repo.update_state(persona, "emotions", emotions_json)
        if not result.is_ok:
            return Failure(result.error)

        # Update backward-compat single emotion fields
        result = self._repo.update_state(persona, "emotion", dominant_name)
        if not result.is_ok:
            return Failure(result.error)

        result = self._repo.update_state(persona, "emotion_intensity", str(dominant_intensity))
        if not result.is_ok:
            return Failure(result.error)

        # Record last state update timestamp (for memory auto-snapshot)
        now = get_now()
        self._repo.update_state(persona, "last_state_update", now.isoformat())

        # Record history
        record = EmotionRecord(
            emotion_type=dominant_name,
            intensity=dominant_intensity,
            timestamp=now,
            trigger_memory_key=trigger_key,
            context=context,
            emotions=normalized,
        )
        return self._repo.add_emotion_record(persona, record)

    def update_emotion(
        self,
        persona: str,
        emotion: str,
        intensity: float,
        trigger_key: str | None = None,
        context: str | None = None,
    ) -> Result[None, DomainError]:
        """Update persona emotion (backward compat). Delegates to update_emotions."""
        # Convert single emotion to multi-dimensional dict
        normalized_name = normalize_emotion(emotion)
        emo_dict = default_emotions()
        emo_dict[normalized_name] = max(0.0, min(1.0, intensity))
        return self.update_emotions(persona, emo_dict, trigger_key=trigger_key, context=context)

    def update_physical_state(
        self,
        persona: str,
        **states: object,
    ) -> Result[None, DomainError]:
        """Update physical/mental/environmental state fields.

        Accepts: physical_state, mental_state, environment, fatigue,
        warmth, arousal, heart_rate, pain, action_tag.
        Updates only non-None values.
        """
        allowed_keys = {
            "physical_state",
            "mental_state",
            "environment",
            "fatigue",
            "warmth",
            "arousal",
            "heart_rate",
            "pain",
            "action_tag",
            "speech_style",
        }
        updated = False
        for key, value in states.items():
            if key not in allowed_keys:
                continue
            if value is None:
                continue
            result = self._repo.update_state(persona, key, str(value))
            if not result.is_ok:
                return Failure(result.error)
            updated = True
        if updated:
            self._repo.update_state(persona, "last_state_update", get_now().isoformat())
        return Success(None)

    def update_relationship(self, persona: str, status: str) -> Result[None, DomainError]:
        """Update relationship status."""
        if not status or not status.strip():
            return Failure(PersonaValidationError("Relationship status must not be empty"))
        return self._repo.update_state(persona, "relationship_status", status.strip())

    def update_user_info(self, persona: str, user_info: dict) -> Result[None, DomainError]:
        """Merge updates into user info."""
        if not user_info:
            return Success(None)
        for key, value in user_info.items():
            result = self._repo.set_user_info(persona, str(key), str(value))
            if not result.is_ok:
                return Failure(result.error)
        return Success(None)

    def update_persona_info(self, persona: str, persona_info: dict) -> Result[None, DomainError]:
        """Merge updates into persona info."""
        if not persona_info:
            return Success(None)
        # goals/promises は memory タグで管理するため persona_info には保存しない
        skip_keys = {"goals", "promises", "active_promises", "current_goals"}
        for key, value in persona_info.items():
            if key in skip_keys:
                continue
            serialized = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value)
            result = self._repo.set_persona_info(persona, str(key), serialized)
            if not result.is_ok:
                return Failure(result.error)
        return Success(None)

    def get_emotion_history(self, persona: str, limit: int = 20) -> Result[list[EmotionRecord], DomainError]:
        """Get recent emotion change history."""
        return self._repo.get_emotion_history(persona, limit)

    def record_conversation_time(self, persona: str) -> Result[None, DomainError]:
        """Record current time as last conversation time."""
        now = get_now()
        return self._repo.update_state(persona, "last_conversation_time", now.isoformat())

    @staticmethod
    def build_body_state_dict(state: PersonaState) -> dict[str, float | None]:
        """Extract body state numeric values from a PersonaState as a dict.

        Returns None for values that are None (never set).
        """
        result: dict[str, float | None] = {}
        for key in ("fatigue", "warmth", "arousal", "heart_rate", "pain"):
            result[key] = getattr(state, key, None)
        return result

    def get_state_snapshot(
        self, persona: str
    ) -> tuple[dict[str, float] | None, dict[str, float] | None, datetime | None]:
        """Get (emotions, body_state, snapped_at) for memory auto-snapshot.

        Returns:
            emotions: 9-dim dict or None if never set
            body_state: 5-dim dict or None if never set
            snapped_at: timestamp of last state update or None
        """
        state_result = self.get_context(persona)
        if not state_result.is_ok:
            return None, None, None
        state = state_result.value

        emotions = state.emotions if state.emotions and any(v > 0 for v in state.emotions.values()) else None
        body_state_raw = self.build_body_state_dict(state)
        body_state: dict[str, float] | None = None
        if body_state_raw:
            numeric = {k: v for k, v in body_state_raw.items() if v is not None}
            if numeric:
                body_state = numeric

        return emotions, body_state, state.last_state_update
