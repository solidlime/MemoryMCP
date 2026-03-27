from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from memory_mcp.domain.persona.entities import (
        ContextEntry,
        EmotionRecord,
        PersonaState,
    )
    from memory_mcp.domain.shared.errors import RepositoryError
    from memory_mcp.domain.shared.result import Result


@runtime_checkable
class PersonaRepository(Protocol):
    """Repository interface for persona state persistence."""

    def get_current_state(self, persona: str) -> Result[PersonaState, RepositoryError]: ...

    def update_state(
        self,
        persona: str,
        key: str,
        value: str,
        source: str | None = None,
    ) -> Result[None, RepositoryError]: ...

    def get_state_history(
        self, persona: str, key: str, limit: int = 20
    ) -> Result[list[ContextEntry], RepositoryError]: ...

    def add_emotion_record(self, persona: str, record: EmotionRecord) -> Result[None, RepositoryError]: ...

    def get_emotion_history(self, persona: str, limit: int = 20) -> Result[list[EmotionRecord], RepositoryError]: ...

    def set_user_info(self, persona: str, key: str, value: str) -> Result[None, RepositoryError]: ...

    def set_persona_info(self, persona: str, key: str, value: str) -> Result[None, RepositoryError]: ...

    def get_user_info(self, persona: str) -> Result[dict, RepositoryError]: ...

    def get_persona_info(self, persona: str) -> Result[dict, RepositoryError]: ...

    def sync_goals(self, persona: str, goals: list) -> Result[None, RepositoryError]: ...

    def sync_promises(self, persona: str, promises: list) -> Result[None, RepositoryError]: ...
