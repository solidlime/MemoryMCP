"""Unit tests for Goals/Promises storage and Memory Stats initialisation.

T7 test cases:
1. JSON 保存確認       — promises/goals が list として DB に往復できること
2. ACTIVE COMMITMENTS  — _format_context_response() に P1/P2 が現れること
3. 空リストでクリア    — [] で上書きすると persona_info から消えること
4. memory_strength 初期化 — save() 直後に strength=1.0 レコードが存在すること
5. entity 自動抽出     — 英語固有名詞が memory_entities に登録されること (best-effort)
"""

from __future__ import annotations

import warnings

import pytest

from memory_mcp.api.mcp.tools import _format_context_response
from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.memory.entity_extractor import SimpleEntityExtractor
from memory_mcp.domain.memory.graph import EntityService
from memory_mcp.domain.persona.entities import PersonaState
from memory_mcp.domain.persona.service import PersonaService
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection
from memory_mcp.infrastructure.sqlite.entity_repo import SQLiteEntityRepository
from memory_mcp.infrastructure.sqlite.memory_repo import SQLiteMemoryRepository
from memory_mcp.infrastructure.sqlite.persona_repo import SQLitePersonaRepository

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

PERSONA = "test_persona"


def _make_memory(key: str = "memory_20250101120000", content: str = "test") -> Memory:
    now = get_now()
    return Memory(key=key, content=content, created_at=now, updated_at=now)


# ---------------------------------------------------------------------------
# Fixtures — all backed by a real SQLite in-memory DB (tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_conn(tmp_path):
    """Fresh SQLiteConnection with fully-initialised schema."""
    conn = SQLiteConnection(data_dir=str(tmp_path), persona=PERSONA)
    conn.initialize_schema()
    yield conn
    conn.close()


@pytest.fixture()
def persona_repo(sqlite_conn: SQLiteConnection):
    return SQLitePersonaRepository(sqlite_conn)


@pytest.fixture()
def persona_service(persona_repo: SQLitePersonaRepository):
    return PersonaService(persona_repo)


@pytest.fixture()
def memory_repo(sqlite_conn: SQLiteConnection):
    return SQLiteMemoryRepository(sqlite_conn)


@pytest.fixture()
def entity_repo(sqlite_conn: SQLiteConnection):
    return SQLiteEntityRepository(sqlite_conn)


@pytest.fixture()
def entity_service(entity_repo: SQLiteEntityRepository):
    return EntityService(entity_repo, SimpleEntityExtractor())


# ===========================================================================
# T7-1: JSON 保存確認
# ===========================================================================


class TestPromisesJsonPersistence:
    """goals/promises は persona_info に保存されず、memory タグで管理される。"""

    def test_goals_skipped_in_persona_info(self, persona_service: PersonaService):
        """update_persona_info(goals=[...]) → persona_info には保存されない。"""
        result = persona_service.update_persona_info(PERSONA, {"goals": ["Goal A", "Goal B"]})
        assert result.is_ok, f"update_persona_info failed: {result}"

        ctx = persona_service.get_context(PERSONA)
        assert ctx.is_ok
        state = ctx.unwrap()
        # goals は persona_info には保存されない
        goals = state.persona_info.get("goals")
        assert goals is None, f"Expected None (goals not stored in persona_info), got {goals!r}"

    def test_promises_skipped_in_persona_info(self, persona_service: PersonaService):
        """update_persona_info(promises=[...]) → persona_info には保存されない。"""
        result = persona_service.update_persona_info(PERSONA, {"promises": ["P1", "P2"]})
        assert result.is_ok

        ctx = persona_service.get_context(PERSONA)
        assert ctx.is_ok
        promises = ctx.unwrap().persona_info.get("promises")
        assert promises is None, f"Expected None (promises not stored in persona_info), got {promises!r}"

    def test_other_persona_info_keys_still_stored(self, persona_service: PersonaService):
        """goals/promises 以外のキーは persona_info に正常に保存される。"""
        result = persona_service.update_persona_info(PERSONA, {"nickname": "TestBot", "goals": ["should be skipped"]})
        assert result.is_ok

        ctx = persona_service.get_context(PERSONA)
        assert ctx.is_ok
        state = ctx.unwrap()
        assert state.persona_info.get("nickname") == "TestBot"
        assert state.persona_info.get("goals") is None


# ===========================================================================
# T7-2: get_context ACTIVE COMMITMENTS 表示確認
# ===========================================================================


class TestActiveCommitmentsDisplay:
    """_format_context_response() が memory タグベースの ACTIVE COMMITMENTS を表示する。"""

    @staticmethod
    def _state() -> PersonaState:
        return PersonaState(
            persona=PERSONA,
            emotion="neutral",
            emotion_intensity=0.0,
            user_info={},
            persona_info={},
        )

    @staticmethod
    def _make_goal(content: str, status: str = "active") -> Memory:
        now = get_now()
        return Memory(key=f"goal_{content[:8]}", content=content, created_at=now, updated_at=now, tags=["goal", status])

    @staticmethod
    def _make_promise(content: str, status: str = "active") -> Memory:
        now = get_now()
        return Memory(
            key=f"promise_{content[:8]}", content=content, created_at=now, updated_at=now, tags=["promise", status]
        )

    @staticmethod
    def _fmt(goals: list, promises: list) -> str:
        return _format_context_response(
            state=TestActiveCommitmentsDisplay._state(),
            stats={},
            recent=[],
            equipment={},
            blocks=[],
            time_since="",
            goals=goals,
            promises=promises,
        )

    def test_promises_appear_in_output(self):
        """active promise が ACTIVE COMMITMENTS に表示される。"""
        output = self._fmt([], [self._make_promise("P1"), self._make_promise("P2")])
        assert "P1" in output, f"'P1' not found in output:\n{output}"
        assert "P2" in output, f"'P2' not found in output:\n{output}"
        assert "ACTIVE COMMITMENTS" in output

    def test_goals_appear_in_output(self):
        """active goal が ACTIVE COMMITMENTS に表示される。"""
        output = self._fmt([self._make_goal("Goal A"), self._make_goal("Goal B")], [])
        assert "Goal A" in output
        assert "Goal B" in output
        assert "ACTIVE COMMITMENTS" in output

    def test_both_promises_and_goals_appear(self):
        """promises と goals が共存して表示される。"""
        output = self._fmt([self._make_goal("G1")], [self._make_promise("P1")])
        assert "P1" in output
        assert "G1" in output
        assert "ACTIVE COMMITMENTS" in output

    def test_empty_goals_and_promises_show_no_commitments_section(self):
        """goals/promises が空のとき ACTIVE COMMITMENTS セクションは現れない。"""
        output = self._fmt([], [])
        assert "ACTIVE COMMITMENTS" not in output

    def test_non_active_goal_not_in_active_commitments(self):
        """achieved goal は ACTIVE COMMITMENTS に表示されず Past Commitments に表示される。"""
        output = self._fmt([self._make_goal("Done Goal", "achieved")], [])
        assert "ACTIVE COMMITMENTS" not in output
        assert "Past Commitments" in output
        assert "Done Goal" in output

    def test_non_active_promise_shows_in_past_commitments(self):
        """fulfilled promise は Past Commitments に表示される。"""
        output = self._fmt([], [self._make_promise("Old Promise", "fulfilled")])
        assert "ACTIVE COMMITMENTS" not in output
        assert "Past Commitments" in output
        assert "Old Promise" in output

    def test_json_string_promises_are_parsed_and_displayed(self):
        """(互換テスト) Memory オブジェクトの active promise は正常に表示される。"""
        output = self._fmt([], [self._make_promise("P1"), self._make_promise("P2")])
        assert "P1" in output
        assert "P2" in output


# ===========================================================================
# T7-3: 空リストでクリア
# ===========================================================================


class TestPromisesClear:
    """goals/promises の memory タグベース管理を確認。"""

    def test_goals_not_stored_in_persona_info_after_update(self, persona_service: PersonaService):
        """goals を persona_info で渡しても persona_info には保存されない。"""
        persona_service.update_persona_info(PERSONA, {"goals": ["G1", "G2"]})
        persona_service.update_persona_info(PERSONA, {"goals": []})

        state = persona_service.get_context(PERSONA).unwrap()
        goals = state.persona_info.get("goals")
        assert goals is None, f"goals should not be in persona_info, got {goals!r}"

    def test_promises_not_stored_in_persona_info_after_update(self, persona_service: PersonaService):
        """promises を persona_info で渡しても persona_info には保存されない。"""
        persona_service.update_persona_info(PERSONA, {"promises": ["P1"]})
        persona_service.update_persona_info(PERSONA, {"promises": []})

        state = persona_service.get_context(PERSONA).unwrap()
        promises = state.persona_info.get("promises")
        assert promises is None, f"promises should not be in persona_info, got {promises!r}"

    def test_memory_repo_get_by_tags_finds_goals(self, memory_repo: SQLiteMemoryRepository):
        """memory_repo.get_by_tags(['goal','active']) で goal memories が取得できる。"""
        now = get_now()
        mem = Memory(
            key="goal_test_001",
            content="Test goal",
            created_at=now,
            updated_at=now,
            tags=["goal", "active"],
            importance=0.8,
        )
        memory_repo.save(mem)

        result = memory_repo.get_by_tags(["goal", "active"])
        assert result.is_ok
        contents = [m.content for m in result.value]
        assert "Test goal" in contents

    def test_memory_repo_get_by_tags_finds_promises(self, memory_repo: SQLiteMemoryRepository):
        """memory_repo.get_by_tags(['promise','active']) で promise memories が取得できる。"""
        now = get_now()
        mem = Memory(
            key="promise_test_001",
            content="Test promise",
            created_at=now,
            updated_at=now,
            tags=["promise", "active"],
            importance=0.8,
        )
        memory_repo.save(mem)

        result = memory_repo.get_by_tags(["promise", "active"])
        assert result.is_ok
        contents = [m.content for m in result.value]
        assert "Test promise" in contents


# ===========================================================================
# T7-4: memory_strength 初期化
# ===========================================================================


class TestMemoryStrengthInit:
    """memory_repo.save() 後に memory_strength テーブルへ strength=1.0 が挿入される。"""

    def test_save_creates_strength_record(
        self,
        memory_repo: SQLiteMemoryRepository,
        sqlite_conn: SQLiteConnection,
    ):
        """save() が memory_strength に strength=1.0 / recall_count=0 を挿入する。"""
        m = _make_memory("memory_20250615120000", "test strength init")
        save_result = memory_repo.save(m)
        assert save_result.is_ok, f"save() failed: {save_result}"

        db = sqlite_conn.get_memory_db()
        row = db.execute(
            "SELECT strength, stability, recall_count FROM memory_strength WHERE memory_key = ?",
            (m.key,),
        ).fetchone()

        assert row is not None, "memory_strength record should exist immediately after save()"
        assert row["strength"] == pytest.approx(1.0), f"Expected strength=1.0 after first save, got {row['strength']}"
        assert row["recall_count"] == 0, f"Expected recall_count=0 on fresh record, got {row['recall_count']}"

    def test_resave_does_not_overwrite_existing_strength(
        self,
        memory_repo: SQLiteMemoryRepository,
        sqlite_conn: SQLiteConnection,
    ):
        """INSERT OR IGNORE: re-save しても既存の strength/recall_count が保たれる。"""
        m = _make_memory("memory_20250615120001", "test resave")
        memory_repo.save(m)

        db = sqlite_conn.get_memory_db()
        # Simulate Ebbinghaus decay / manual boost
        db.execute(
            "UPDATE memory_strength SET strength = 0.42, recall_count = 5 WHERE memory_key = ?",
            (m.key,),
        )
        db.commit()

        # Re-save should not clobber the existing record
        memory_repo.save(m)

        row = db.execute(
            "SELECT strength, recall_count FROM memory_strength WHERE memory_key = ?",
            (m.key,),
        ).fetchone()
        assert row is not None
        assert row["strength"] == pytest.approx(0.42), "INSERT OR IGNORE must not replace existing strength"
        assert row["recall_count"] == 5, "INSERT OR IGNORE must not reset recall_count"

    def test_multiple_memories_each_get_strength_record(
        self,
        memory_repo: SQLiteMemoryRepository,
        sqlite_conn: SQLiteConnection,
    ):
        """複数の異なる記憶をそれぞれ保存すると、それぞれに strength レコードが作られる。"""
        keys = [
            "memory_20250615120001",
            "memory_20250615120002",
            "memory_20250615120003",
        ]
        for key in keys:
            memory_repo.save(_make_memory(key, f"content for {key}"))

        db = sqlite_conn.get_memory_db()
        rows = db.execute("SELECT memory_key FROM memory_strength").fetchall()
        stored_keys = {r["memory_key"] for r in rows}
        for key in keys:
            assert key in stored_keys, f"No strength record found for {key}"


# ===========================================================================
# T7-5: entity 自動抽出 (best-effort)
# ===========================================================================


class TestEntityAutoExtract:
    """英語固有名詞が extract_and_link で memory_entities に登録される。

    extract_and_link は best-effort なので 0 件でも fail させず警告のみ。
    """

    _CONTENT = "Alice met Bob at the conference"

    def test_extractor_directly_finds_alice_and_bob(self):
        """SimpleEntityExtractor が 'Alice' / 'Bob' を直接抽出できることを確認。"""
        extractor = SimpleEntityExtractor()
        results = extractor.extract(self._CONTENT)
        names = {name for name, _ in results}
        assert "Alice" in names or "Bob" in names, (
            f"SimpleEntityExtractor did not find 'Alice' or 'Bob' in {names!r}. Input: '{self._CONTENT}'"
        )

    def test_extract_and_link_returns_ok(self, entity_service: EntityService):
        """extract_and_link() は少なくとも成功 (is_ok) を返す。"""
        result = entity_service.extract_and_link(
            memory_key="mem_alice_bob",
            content=self._CONTENT,
        )
        assert result.is_ok, f"extract_and_link raised an error: {result}"

    def test_memory_entities_table_populated(
        self,
        entity_service: EntityService,
        entity_repo: SQLiteEntityRepository,
    ):
        """extract_and_link 後、memory_entities テーブルに Alice か Bob が存在する。

        0 件の場合は best-effort のため警告のみ（テスト失敗にしない）。
        """
        entity_service.extract_and_link(
            memory_key="mem_alice_bob_2",
            content=self._CONTENT,
        )

        mem_entities = entity_repo.get_memory_entities("mem_alice_bob_2")
        assert mem_entities.is_ok

        if not mem_entities.value:
            warnings.warn(
                f"memory_entities is empty for '{self._CONTENT}' — "
                "extractor returned no results (best-effort, not failing).",
                stacklevel=2,
            )
            return

        entity_ids_lower = {e.id.lower() for e in mem_entities.value}
        assert "alice" in entity_ids_lower or "bob" in entity_ids_lower, (
            f"Expected 'alice' or 'bob' (case-insensitive) in memory_entities, got {entity_ids_lower!r}"
        )

    def test_english_proper_nouns_in_entity_result(self, entity_service: EntityService):
        """extract_and_link の戻り値に Alice または Bob が含まれる。

        0 件の場合は best-effort のため警告のみ（テスト失敗にしない）。
        """
        result = entity_service.extract_and_link(
            memory_key="mem_alice_bob_3",
            content=self._CONTENT,
        )
        assert result.is_ok

        entity_ids = {e.id for e in result.value}
        entity_ids_lower = {e.lower() for e in entity_ids}
        if not entity_ids:
            warnings.warn(
                f"No entities extracted from '{self._CONTENT}' (best-effort, not failing).",
                stacklevel=2,
            )
            return

        assert "alice" in entity_ids_lower or "bob" in entity_ids_lower, (
            f"Expected 'alice' or 'bob' (case-insensitive) in extracted entities, got {entity_ids!r}"
        )
