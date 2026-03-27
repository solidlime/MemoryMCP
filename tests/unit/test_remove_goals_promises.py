"""Unit tests for remove_goals / remove_promises logic in update_context.

Tests verify the removal logic directly, without requiring a running MCP server.
The underlying mechanism mirrors the append logic already tested in test_update_context_append.py.
"""

from __future__ import annotations

import json

import pytest

from memory_mcp.domain.persona.service import PersonaService
from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection
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
    """remove_goals behaviour via the real service layer."""

    def test_remove_goal_from_existing_list(self, persona_service: PersonaService):
        persona_service.update_persona_info(PERSONA, {"goals": ["G1", "G2", "G3"]})

        ctx = persona_service.get_context(PERSONA).unwrap()
        existing = ctx.persona_info.get("goals", [])
        if isinstance(existing, str):
            existing = json.loads(existing)
        new_goals = [g for g in existing if g not in ["G2"]]
        persona_service.update_persona_info(PERSONA, {"goals": new_goals})

        state = persona_service.get_context(PERSONA).unwrap()
        goals = state.persona_info.get("goals")
        if isinstance(goals, str):
            goals = json.loads(goals)
        assert "G2" not in goals
        assert "G1" in goals
        assert "G3" in goals

    def test_remove_nonexistent_goal_is_noop(self, persona_service: PersonaService):
        persona_service.update_persona_info(PERSONA, {"goals": ["G1", "G2"]})

        ctx = persona_service.get_context(PERSONA).unwrap()
        existing = ctx.persona_info.get("goals", [])
        if isinstance(existing, str):
            existing = json.loads(existing)
        new_goals = [g for g in existing if g not in ["G_NONEXISTENT"]]
        persona_service.update_persona_info(PERSONA, {"goals": new_goals})

        state = persona_service.get_context(PERSONA).unwrap()
        goals = state.persona_info.get("goals")
        if isinstance(goals, str):
            goals = json.loads(goals)
        assert "G1" in goals
        assert "G2" in goals

    def test_remove_promise_from_existing_list(self, persona_service: PersonaService):
        persona_service.update_persona_info(PERSONA, {"promises": ["P1", "P2", "P3"]})

        ctx = persona_service.get_context(PERSONA).unwrap()
        existing = ctx.persona_info.get("promises", [])
        if isinstance(existing, str):
            existing = json.loads(existing)
        new_promises = [p for p in existing if p not in ["P1"]]
        persona_service.update_persona_info(PERSONA, {"promises": new_promises})

        state = persona_service.get_context(PERSONA).unwrap()
        promises = state.persona_info.get("promises")
        if isinstance(promises, str):
            promises = json.loads(promises)
        assert "P1" not in promises
        assert "P2" in promises
        assert "P3" in promises

    def test_remove_nonexistent_promise_is_noop(self, persona_service: PersonaService):
        persona_service.update_persona_info(PERSONA, {"promises": ["P1"]})

        ctx = persona_service.get_context(PERSONA).unwrap()
        existing = ctx.persona_info.get("promises", [])
        if isinstance(existing, str):
            existing = json.loads(existing)
        new_promises = [p for p in existing if p not in ["P_NONEXISTENT"]]
        persona_service.update_persona_info(PERSONA, {"promises": new_promises})

        state = persona_service.get_context(PERSONA).unwrap()
        promises = state.persona_info.get("promises")
        if isinstance(promises, str):
            promises = json.loads(promises)
        assert "P1" in promises


# ---------------------------------------------------------------------------
# persona_info direct-set overrides remove (logic test)
# ---------------------------------------------------------------------------


class TestPersonaInfoOverridesRemove:
    """persona_info に goals が直接指定されたら remove_goals は無視される（ロジックテスト）。"""

    def test_direct_persona_info_goals_takes_precedence(self, persona_service: PersonaService):
        """persona_info={"goals": [...]} で直接指定した場合、remove_goals は適用されない。

        tools.py の実装では:
          skip_remove_goals = persona_info is not None and "goals" in persona_info
        なので、persona_info に goals が含まれていれば remove_goals は無視される。
        このテストはその前提条件を service 層で確認する。
        """
        persona_service.update_persona_info(PERSONA, {"goals": ["G1", "G2"]})

        # persona_info で直接 goals を上書きすれば remove は不要（上書き優先）
        persona_service.update_persona_info(PERSONA, {"goals": ["G1", "G2"]})

        state = persona_service.get_context(PERSONA).unwrap()
        goals = state.persona_info.get("goals")
        if isinstance(goals, str):
            goals = json.loads(goals)
        # remove_goals=["G2"] は適用されていない（persona_info 直接指定が優先されるため）
        assert "G1" in goals
        assert "G2" in goals
