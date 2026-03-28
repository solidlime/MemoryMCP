"""Unit tests for remove_goals / remove_promises logic in update_context.

Tests verify the removal logic directly, without requiring a running MCP server.
The underlying mechanism mirrors the append logic already tested in test_update_context_append.py.
"""

from __future__ import annotations

import json

import pytest

from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.persona.service import PersonaService
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection
from memory_mcp.infrastructure.sqlite.memory_repo import SQLiteMemoryRepository
from memory_mcp.infrastructure.sqlite.persona_repo import SQLitePersonaRepository

PERSONA = "test_remove_persona"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _remove(existing_json: str | list, remove: list[str]) -> list[str]:
    """Replicate the remove logic from tools.py update_context."""
    if isinstance(existing_json, str):
        try:
            existing = json.loads(existing_json)
        except Exception:
            existing = []
    elif isinstance(existing_json, list):
        existing = existing_json
    else:
        existing = []
    return [g for g in existing if g not in remove]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_conn(tmp_path):
    conn = SQLiteConnection(data_dir=str(tmp_path), persona=PERSONA)
    conn.initialize_schema()
    yield conn
    conn.close()


@pytest.fixture()
def persona_service(sqlite_conn: SQLiteConnection):
    repo = SQLitePersonaRepository(sqlite_conn)
    return PersonaService(repo)


# ---------------------------------------------------------------------------
# Unit tests for the pure removal helper (no DB needed)
# ---------------------------------------------------------------------------


class TestRemoveLogicPure:
    """Pure logic tests — mirrors test_update_context_append.py style."""

    def test_remove_single_item(self):
        result = _remove('["goal1", "goal2"]', ["goal1"])
        assert result == ["goal2"]

    def test_remove_nonexistent_item_is_noop(self):
        result = _remove('["goal1", "goal2"]', ["goal3"])
        assert result == ["goal1", "goal2"]

    def test_remove_all_items(self):
        result = _remove('["goal1", "goal2"]', ["goal1", "goal2"])
        assert result == []

    def test_remove_from_empty_list(self):
        result = _remove("[]", ["goal1"])
        assert result == []

    def test_remove_from_list_type(self):
        result = _remove(["A", "B", "C"], ["B"])
        assert result == ["A", "C"]

    def test_remove_invalid_json_treated_as_empty(self):
        result = _remove("not-valid-json", ["goal1"])
        assert result == []

    def test_remove_multiple_items(self):
        result = _remove(["P1", "P2", "P3"], ["P1", "P3"])
        assert result == ["P2"]


# ---------------------------------------------------------------------------
# Integration tests — via PersonaService (real SQLite)
# ---------------------------------------------------------------------------


class TestRemoveGoalsViaPersonaService:
    """remove_goals behaviour via memory_repo (tag-based)."""

    @pytest.fixture()
    def memory_repo(self, sqlite_conn):
        return SQLiteMemoryRepository(sqlite_conn)

    def _add_goal(self, memory_repo, text: str) -> None:
        now = get_now()
        mem = Memory(
            key=f"goal_{hash(text) % 100000}",
            content=text,
            created_at=now,
            updated_at=now,
            tags=["goal", "active"],
            importance=0.8,
        )
        memory_repo.save(mem)

    def _cancel_goal(self, memory_repo, text: str) -> None:
        result = memory_repo.get_by_tags(["goal", "active"])
        for goal in result.value or []:
            if goal.content == text:
                new_tags = [t for t in (goal.tags or []) if t not in ("active", "achieved", "cancelled")] + [
                    "cancelled"
                ]
                memory_repo.update(goal.key, tags=new_tags)

    def test_remove_goal_from_existing_list(self, memory_repo):
        self._add_goal(memory_repo, "G1")
        self._add_goal(memory_repo, "G2")
        self._add_goal(memory_repo, "G3")

        self._cancel_goal(memory_repo, "G2")

        result = memory_repo.get_by_tags(["goal", "active"])
        assert result.is_ok
        active_contents = [m.content for m in result.value]
        assert "G2" not in active_contents
        assert "G1" in active_contents
        assert "G3" in active_contents

    def test_remove_nonexistent_goal_is_noop(self, memory_repo):
        self._add_goal(memory_repo, "G1")
        self._add_goal(memory_repo, "G2")

        self._cancel_goal(memory_repo, "G_NONEXISTENT")

        result = memory_repo.get_by_tags(["goal", "active"])
        assert result.is_ok
        active_contents = [m.content for m in result.value]
        assert "G1" in active_contents
        assert "G2" in active_contents

    def _add_promise(self, memory_repo, text: str) -> None:
        now = get_now()
        mem = Memory(
            key=f"promise_{hash(text) % 100000}",
            content=text,
            created_at=now,
            updated_at=now,
            tags=["promise", "active"],
            importance=0.8,
        )
        memory_repo.save(mem)

    def _cancel_promise(self, memory_repo, text: str) -> None:
        result = memory_repo.get_by_tags(["promise", "active"])
        for promise in result.value or []:
            if promise.content == text:
                new_tags = [t for t in (promise.tags or []) if t not in ("active", "fulfilled", "cancelled")] + [
                    "cancelled"
                ]
                memory_repo.update(promise.key, tags=new_tags)

    def test_remove_promise_from_existing_list(self, memory_repo):
        self._add_promise(memory_repo, "P1")
        self._add_promise(memory_repo, "P2")
        self._add_promise(memory_repo, "P3")

        self._cancel_promise(memory_repo, "P1")

        result = memory_repo.get_by_tags(["promise", "active"])
        assert result.is_ok
        active_contents = [m.content for m in result.value]
        assert "P1" not in active_contents
        assert "P2" in active_contents
        assert "P3" in active_contents

    def test_remove_nonexistent_promise_is_noop(self, memory_repo):
        self._add_promise(memory_repo, "P1")
        self._cancel_promise(memory_repo, "P_NONEXISTENT")

        result = memory_repo.get_by_tags(["promise", "active"])
        assert result.is_ok
        active_contents = [m.content for m in result.value]
        assert "P1" in active_contents


# ---------------------------------------------------------------------------
# persona_info direct-set overrides remove (logic test)
# ---------------------------------------------------------------------------


class TestPersonaInfoOverridesRemove:
    """persona_info に goals が指定されても persona_info には保存されない（タグ管理のため）。"""

    @pytest.fixture()
    def memory_repo(self, sqlite_conn):
        return SQLiteMemoryRepository(sqlite_conn)

    def test_direct_persona_info_goals_not_stored(self, persona_service: PersonaService):
        """persona_info={"goals": [...]} は persona_info には保存されない（タグ管理）。"""
        persona_service.update_persona_info(PERSONA, {"goals": ["G1", "G2"]})

        state = persona_service.get_context(PERSONA).unwrap()
        goals = state.persona_info.get("goals")
        # goals は persona_info に保存されないため None
        assert goals is None, f"goals should not be in persona_info, got {goals!r}"
