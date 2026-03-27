from __future__ import annotations

import json
from typing import TYPE_CHECKING

from memory_mcp.domain.persona.entities import EmotionRecord, PersonaState
from memory_mcp.domain.shared.errors import DomainError, PersonaValidationError
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.domain.value_objects import normalize_emotion

if TYPE_CHECKING:
    from memory_mcp.domain.persona.repository import PersonaRepository


class PersonaService:
    """Domain service for persona state management."""

    def __init__(self, repo: PersonaRepository) -> None:
        self._repo = repo

    def get_context(self, persona: str) -> Result[PersonaState, DomainError]:
        """Get current persona state."""
        return self._repo.get_current_state(persona)

    def update_emotion(
        self,
        persona: str,
        emotion: str,
        intensity: float,
        trigger_key: str | None = None,
        context: str | None = None,
    ) -> Result[None, DomainError]:
        """Update persona emotion and record in history."""
        emotion = normalize_emotion(emotion)
        intensity = max(0.0, min(1.0, intensity))

        state_result = self._repo.update_state(persona, "emotion", emotion)
        if not state_result.is_ok:
            return Failure(state_result.error)

        intensity_result = self._repo.update_state(persona, "emotion_intensity", str(intensity))
        if not intensity_result.is_ok:
            return Failure(intensity_result.error)

        record = EmotionRecord(
            emotion_type=emotion,
            intensity=intensity,
            timestamp=get_now(),
            trigger_memory_key=trigger_key,
            context=context,
        )
        return self._repo.add_emotion_record(persona, record)

    def update_physical_state(
        self,
        persona: str,
        **states: object,
    ) -> Result[None, DomainError]:
        """Update physical/mental/environmental state fields.

        Accepts: physical_state, mental_state, environment, fatigue,
        warmth, arousal, heart_rate, touch_response, action_tag.
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
            "touch_response",
            "action_tag",
            "speech_style",
        }
        for key, value in states.items():
            if key not in allowed_keys:
                continue
            if value is None:
                continue
            result = self._repo.update_state(persona, key, str(value))
            if not result.is_ok:
                return Failure(result.error)
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
        for key, value in persona_info.items():
            # JSON シリアライズ（リストや辞書を正しく保存）
            serialized = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value)
            result = self._repo.set_persona_info(persona, str(key), serialized)
            if not result.is_ok:
                return Failure(result.error)

        # goals/promises テーブルへの同期
        self._sync_goals_promises(persona, persona_info)
        return Success(None)

    def _sync_goals_promises(self, persona: str, persona_info: dict) -> None:
        """goals/promises テーブルに persona_info の内容を同期する（best-effort）。"""
        import contextlib

        with contextlib.suppress(Exception):
            if "goals" in persona_info:
                self._repo.sync_goals(persona, persona_info["goals"])
            if "promises" in persona_info:
                self._repo.sync_promises(persona, persona_info["promises"])

    def record_conversation_time(self, persona: str) -> Result[None, DomainError]:
        """Record current time as last conversation time."""
        now = get_now()
        return self._repo.update_state(persona, "last_conversation_time", now.isoformat())
