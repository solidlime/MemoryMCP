"""Tests for PersonaService with an InMemory repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from memory_mcp.domain.persona.entities import (
    ContextEntry,
    EmotionRecord,
    PersonaState,
)
from memory_mcp.domain.persona.service import PersonaService
from memory_mcp.domain.shared.result import Result, Success

if TYPE_CHECKING:
    from memory_mcp.domain.shared.errors import RepositoryError

# ---------------------------------------------------------------------------
# InMemory PersonaRepository
# ---------------------------------------------------------------------------


class InMemoryPersonaRepository:
    """Protocol-compatible in-memory repo for PersonaService tests."""

    def __init__(self) -> None:
        self._state: dict[str, dict[str, str]] = {}
        self._emotions: dict[str, list[EmotionRecord]] = {}
        self._user_info: dict[str, dict[str, str]] = {}
        self._persona_info: dict[str, dict[str, str]] = {}

    def get_current_state(self, persona: str) -> Result[PersonaState, RepositoryError]:
        state_map = self._state.get(persona, {})
        user_info = self._user_info.get(persona, {})
        persona_info = self._persona_info.get(persona, {})
        return Success(
            PersonaState(
                persona=persona,
                emotion=state_map.get("emotion", "neutral"),
                emotion_intensity=float(state_map.get("emotion_intensity", "0.0")),
                physical_state=state_map.get("physical_state"),
                mental_state=state_map.get("mental_state"),
                environment=state_map.get("environment"),
                relationship_status=state_map.get("relationship_status"),
                user_info=user_info,
                persona_info=persona_info,
            )
        )

    def update_state(
        self,
        persona: str,
        key: str,
        value: str,
        source: str | None = None,
    ) -> Result[None, RepositoryError]:
        if persona not in self._state:
            self._state[persona] = {}
        self._state[persona][key] = value
        return Success(None)

    def get_state_history(self, persona: str, key: str, limit: int = 20) -> Result[list[ContextEntry], RepositoryError]:
        return Success([])

    def add_emotion_record(self, persona: str, record: EmotionRecord) -> Result[None, RepositoryError]:
        if persona not in self._emotions:
            self._emotions[persona] = []
        self._emotions[persona].append(record)
        return Success(None)

    def get_emotion_history(self, persona: str, limit: int = 20) -> Result[list[EmotionRecord], RepositoryError]:
        records = self._emotions.get(persona, [])
        return Success(records[-limit:])

    def set_user_info(self, persona: str, key: str, value: str) -> Result[None, RepositoryError]:
        if persona not in self._user_info:
            self._user_info[persona] = {}
        self._user_info[persona][key] = value
        return Success(None)

    def set_persona_info(self, persona: str, key: str, value: str) -> Result[None, RepositoryError]:
        if persona not in self._persona_info:
            self._persona_info[persona] = {}
        self._persona_info[persona][key] = value
        return Success(None)

    def get_user_info(self, persona: str) -> Result[dict, RepositoryError]:
        return Success(self._user_info.get(persona, {}))

    def get_persona_info(self, persona: str) -> Result[dict, RepositoryError]:
        return Success(self._persona_info.get(persona, {}))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PERSONA = "test_persona"


@pytest.fixture
def repo():
    return InMemoryPersonaRepository()


@pytest.fixture
def service(repo):
    return PersonaService(repo)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetContext:
    def test_default_state(self, service: PersonaService):
        result = service.get_context(PERSONA)
        assert result.is_ok
        state = result.unwrap()
        assert state.persona == PERSONA
        assert state.emotion == "neutral"
        assert state.emotion_intensity == 0.0

    def test_reflects_updates(self, service: PersonaService):
        service.update_emotion(PERSONA, "joy", 0.8)
        result = service.get_context(PERSONA)
        assert result.is_ok
        state = result.unwrap()
        assert state.emotion == "joy"


class TestUpdateEmotion:
    def test_updates_emotion(self, service: PersonaService, repo: InMemoryPersonaRepository):
        result = service.update_emotion(PERSONA, "joy", 0.8)
        assert result.is_ok
        assert repo._state[PERSONA]["emotion"] == "joy"
        assert repo._state[PERSONA]["emotion_intensity"] == "0.8"

    def test_records_in_history(self, service: PersonaService, repo: InMemoryPersonaRepository):
        service.update_emotion(PERSONA, "sadness", 0.6, context="rain")
        records = repo._emotions[PERSONA]
        assert len(records) == 1
        assert records[0].emotion_type == "sadness"
        assert records[0].context == "rain"

    def test_clamps_intensity(self, service: PersonaService, repo: InMemoryPersonaRepository):
        service.update_emotion(PERSONA, "anger", 1.5)
        assert repo._state[PERSONA]["emotion_intensity"] == "1.0"

    def test_empty_emotion_fails(self, service: PersonaService):
        result = service.update_emotion(PERSONA, "", 0.5)
        assert not result.is_ok


class TestUpdatePhysicalState:
    def test_updates_fields(self, service: PersonaService, repo: InMemoryPersonaRepository):
        result = service.update_physical_state(PERSONA, physical_state="tired", mental_state="calm")
        assert result.is_ok
        assert repo._state[PERSONA]["physical_state"] == "tired"
        assert repo._state[PERSONA]["mental_state"] == "calm"

    def test_ignores_none_values(self, service: PersonaService, repo: InMemoryPersonaRepository):
        service.update_physical_state(PERSONA, physical_state="ok")
        result = service.update_physical_state(PERSONA, physical_state=None, mental_state="happy")
        assert result.is_ok
        # physical_state should remain "ok"
        assert repo._state[PERSONA]["physical_state"] == "ok"
        assert repo._state[PERSONA]["mental_state"] == "happy"

    def test_ignores_unknown_keys(self, service: PersonaService, repo: InMemoryPersonaRepository):
        result = service.update_physical_state(PERSONA, unknown_key="value")
        assert result.is_ok
        assert "unknown_key" not in repo._state.get(PERSONA, {})


class TestUpdateRelationship:
    def test_updates_status(self, service: PersonaService, repo: InMemoryPersonaRepository):
        result = service.update_relationship(PERSONA, "恋人")
        assert result.is_ok
        assert repo._state[PERSONA]["relationship_status"] == "恋人"

    def test_empty_status_fails(self, service: PersonaService):
        result = service.update_relationship(PERSONA, "")
        assert not result.is_ok


class TestUpdateUserInfo:
    def test_sets_user_info(self, service: PersonaService, repo: InMemoryPersonaRepository):
        result = service.update_user_info(PERSONA, {"name": "太郎", "age": "25"})
        assert result.is_ok
        assert repo._user_info[PERSONA]["name"] == "太郎"
        assert repo._user_info[PERSONA]["age"] == "25"

    def test_empty_dict_noop(self, service: PersonaService):
        result = service.update_user_info(PERSONA, {})
        assert result.is_ok


class TestUpdatePersonaInfo:
    def test_sets_persona_info(self, service: PersonaService, repo: InMemoryPersonaRepository):
        result = service.update_persona_info(PERSONA, {"nickname": "ヘルタ"})
        assert result.is_ok
        assert repo._persona_info[PERSONA]["nickname"] == "ヘルタ"


class TestRecordConversationTime:
    def test_records_time(self, service: PersonaService, repo: InMemoryPersonaRepository):
        result = service.record_conversation_time(PERSONA)
        assert result.is_ok
        assert "last_conversation_time" in repo._state.get(PERSONA, {})
