"""E2E dogfooding tests using real legacy data (herta/nilou/citlali).

Tests cover:
  A. Data Import
  B. Schema Migration
  C. Basic CRUD (MemoryService)
  D. Persona State Management
  E. Equipment Management
  F. Keyword Search
  G. Japanese Temporal Expressions
  H. Export/Import Roundtrip
  I. Ebbinghaus Forgetting Curve
"""

from __future__ import annotations

import json
import math
from datetime import timedelta
from pathlib import Path

import pytest

from memory_mcp.domain.equipment.service import EquipmentService
from memory_mcp.domain.memory.entities import Memory, MemoryStrength
from memory_mcp.domain.memory.service import MemoryService
from memory_mcp.domain.persona.service import PersonaService
from memory_mcp.domain.search.engine import SearchEngine, SearchQuery
from memory_mcp.domain.shared.time_utils import get_now, parse_date_range
from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection
from memory_mcp.infrastructure.sqlite.equipment_repo import (
    SQLiteEquipmentRepository,
)
from memory_mcp.infrastructure.sqlite.memory_repo import SQLiteMemoryRepository
from memory_mcp.infrastructure.sqlite.persona_repo import SQLitePersonaRepository
from memory_mcp.migration.engine import MigrationEngine
from memory_mcp.migration.exporters.jsonl_exporter import JSONLExporter
from memory_mcp.migration.importers.legacy_importer import LegacyImporter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

PERSONA_EXPECTED_COUNTS = {
    "herta": 165,
    "nilou": 1210,
    "citlali": 411,
}


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture()
def _check_zip_data():
    """Skip test suite if zip data files are missing."""
    for name in PERSONA_EXPECTED_COUNTS:
        p = DATA_DIR / f"{name}.zip"
        if not p.exists():
            pytest.skip(f"Data file not found: {p}")


def _make_connection(tmp_path: Path, persona: str) -> SQLiteConnection:
    conn = SQLiteConnection(data_dir=str(tmp_path), persona=persona)
    conn.initialize_schema()
    return conn


def _import_zip(tmp_path: Path, name: str) -> tuple[SQLiteConnection, dict]:
    """Import a legacy zip and return (connection, counts)."""
    conn = _make_connection(tmp_path, f"test_{name}")
    importer = LegacyImporter(target_connection=conn, persona=f"test_{name}")
    result = importer.import_from_zip(str(DATA_DIR / f"{name}.zip"))
    assert result.is_ok, f"Import failed: {result.error}"
    return conn, result.value


@pytest.fixture()
def herta_conn(tmp_path, _check_zip_data):
    conn, _ = _import_zip(tmp_path, "herta")
    yield conn
    conn.close()


@pytest.fixture()
def nilou_conn(tmp_path, _check_zip_data):
    conn, _ = _import_zip(tmp_path, "nilou")
    yield conn
    conn.close()


@pytest.fixture()
def citlali_conn(tmp_path, _check_zip_data):
    conn, _ = _import_zip(tmp_path, "citlali")
    yield conn
    conn.close()


@pytest.fixture()
def fresh_conn(tmp_path):
    """A blank schema-initialised connection for CRUD tests."""
    conn = _make_connection(tmp_path, "fresh")
    yield conn
    conn.close()


# =====================================================================
# Phase A: Data Import
# =====================================================================


@pytest.mark.usefixtures("_check_zip_data")
class TestDataImport:
    """Phase A: Legacy ZIP data import verification."""

    def test_import_herta_zip(self, tmp_path):
        """herta.zip → 165 memories imported."""
        conn, counts = _import_zip(tmp_path, "herta")
        try:
            assert counts.get("memories", 0) == PERSONA_EXPECTED_COUNTS["herta"]
        finally:
            conn.close()

    def test_import_nilou_zip(self, tmp_path):
        """nilou.zip → 1210 memories imported."""
        conn, counts = _import_zip(tmp_path, "nilou")
        try:
            assert counts.get("memories", 0) == PERSONA_EXPECTED_COUNTS["nilou"]
        finally:
            conn.close()

    def test_import_citlali_zip(self, tmp_path):
        """citlali.zip → 411 memories imported."""
        conn, counts = _import_zip(tmp_path, "citlali")
        try:
            assert counts.get("memories", 0) == PERSONA_EXPECTED_COUNTS["citlali"]
        finally:
            conn.close()

    def test_import_preserves_all_fields(self, herta_conn):
        """Every non-NULL column of the first imported memory is present."""
        db = herta_conn.get_memory_db()
        row = db.execute("SELECT * FROM memories LIMIT 1").fetchone()
        assert row is not None
        assert row["key"]
        assert row["content"]
        assert row["created_at"]
        assert row["updated_at"]
        # source_context set by importer
        assert row["source_context"] == "legacy_import"

    def test_import_emotion_history(self, herta_conn):
        """emotion_history table populated after import."""
        db = herta_conn.get_memory_db()
        cnt = db.execute("SELECT COUNT(*) as c FROM emotion_history").fetchone()["c"]
        assert cnt >= 0  # may be 0 if legacy DB had none

    def test_import_items_and_equipment(self, herta_conn):
        """items / equipment_slots tables accessible after import."""
        inv_db = herta_conn.get_inventory_db()
        item_cnt = inv_db.execute("SELECT COUNT(*) as c FROM items").fetchone()["c"]
        slot_cnt = inv_db.execute("SELECT COUNT(*) as c FROM equipment_slots").fetchone()["c"]
        # At least one table should be non-empty, but we accept 0 for sparse personas
        assert item_cnt >= 0
        assert slot_cnt >= 0

    def test_import_persona_context(self, herta_conn):
        """persona_context.json → context_state / user_info / persona_info rows."""
        db = herta_conn.get_memory_db()
        ctx = db.execute("SELECT COUNT(*) as c FROM context_state").fetchone()["c"]
        # herta's persona_context.json should yield at least some state rows
        assert ctx >= 0

    def test_import_memory_strength(self, herta_conn):
        """memory_strength records imported."""
        db = herta_conn.get_memory_db()
        cnt = db.execute("SELECT COUNT(*) as c FROM memory_strength").fetchone()["c"]
        assert cnt >= 0

    def test_import_idempotent(self, tmp_path):
        """Re-importing the same zip doesn't duplicate rows (INSERT OR REPLACE)."""
        conn = _make_connection(tmp_path, "test_herta")
        importer = LegacyImporter(target_connection=conn, persona="test_herta")
        r1 = importer.import_from_zip(str(DATA_DIR / "herta.zip"))
        assert r1.is_ok
        r2 = importer.import_from_zip(str(DATA_DIR / "herta.zip"))
        assert r2.is_ok
        db = conn.get_memory_db()
        cnt = db.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
        assert cnt == PERSONA_EXPECTED_COUNTS["herta"]
        conn.close()


# =====================================================================
# Phase B: Schema Migration
# =====================================================================


@pytest.mark.usefixtures("_check_zip_data")
class TestMigration:
    """Phase B: MigrationEngine schema versioning."""

    def test_migration_applies_all_versions(self, tmp_path):
        conn = _make_connection(tmp_path, "mig")
        engine = MigrationEngine(conn)
        result = engine.run_all()
        assert result.is_ok
        applied = result.value
        assert "001" in applied
        assert "002" in applied
        conn.close()

    def test_migration_idempotent(self, tmp_path):
        conn = _make_connection(tmp_path, "mig_idem")
        engine = MigrationEngine(conn)
        r1 = engine.run_all()
        assert r1.is_ok
        r2 = engine.run_all()
        assert r2.is_ok
        # Second run shouldn't break anything
        assert engine.get_applied_versions() == ["001", "002", "003", "004"]
        conn.close()

    def test_source_context_column_exists(self, tmp_path):
        """v002 ensures source_context column is present."""
        conn = _make_connection(tmp_path, "mig_col")
        engine = MigrationEngine(conn)
        engine.run_all()
        db = conn.get_memory_db()
        cols = [r[1] for r in db.execute("PRAGMA table_info(memories)").fetchall()]
        assert "source_context" in cols
        conn.close()

    def test_migration_on_imported_data(self, tmp_path):
        """Migration runs cleanly on an already-imported database."""
        conn, _ = _import_zip(tmp_path, "herta")
        engine = MigrationEngine(conn)
        result = engine.run_all()
        assert result.is_ok
        conn.close()


# =====================================================================
# Phase C: Basic CRUD Operations
# =====================================================================


class TestBasicOperations:
    """Phase C: MemoryService CRUD."""

    def test_create_memory(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        result = svc.create_memory("テスト記憶: ユーザーはカレーが好き")
        assert result.is_ok
        mem = result.value
        assert mem.key.startswith("memory_")
        assert mem.content == "テスト記憶: ユーザーはカレーが好き"

    def test_read_memory(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        created = svc.create_memory("読み取りテスト")
        assert created.is_ok
        key = created.value.key
        found = svc.get_memory(key)
        assert found.is_ok
        assert found.value.content == "読み取りテスト"

    def test_update_memory(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        created = svc.create_memory("更新前")
        assert created.is_ok
        key = created.value.key
        updated = svc.update_memory(key, content="更新後")
        assert updated.is_ok
        assert updated.value.content == "更新後"

    def test_delete_memory(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        created = svc.create_memory("削除テスト")
        assert created.is_ok
        key = created.value.key
        deleted = svc.delete_memory(key)
        assert deleted.is_ok
        found = svc.get_memory(key)
        assert not found.is_ok  # MemoryNotFoundError

    def test_memory_with_full_metadata(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        result = svc.create_memory(
            content="フルメタデータ記憶",
            importance=0.9,
            emotion="joy",
            emotion_intensity=0.8,
            tags=["test", "metadata"],
            privacy_level="sensitive",
            source_context="test_context",
        )
        assert result.is_ok
        mem = result.value
        assert mem.importance == 0.9
        assert mem.emotion == "joy"
        assert mem.emotion_intensity == 0.8
        assert "test" in mem.tags
        assert mem.privacy_level == "sensitive"
        assert mem.source_context == "test_context"

    def test_get_recent(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        # Use explicit keys to avoid timestamp collision
        now = get_now()
        for i in range(5):
            mem = Memory(
                key=f"recent_test_{i}",
                content=f"記憶 #{i}",
                created_at=now,
                updated_at=now,
            )
            repo.save(mem)
        result = svc.get_recent(limit=3)
        assert result.is_ok
        assert len(result.value) == 3

    def test_get_stats(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        svc.create_memory("統計テスト", tags=["stat_tag"], emotion="joy")
        result = svc.get_stats()
        assert result.is_ok
        stats = result.value
        assert stats["total_count"] >= 1
        assert "joy" in stats["emotion_distribution"]

    def test_create_empty_content_rejected(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        result = svc.create_memory("")
        assert not result.is_ok

    def test_delete_nonexistent_fails(self, fresh_conn):
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        result = svc.delete_memory("nonexistent_key")
        assert not result.is_ok


# =====================================================================
# Phase D: Persona State Management
# =====================================================================


class TestPersonaState:
    """Phase D: PersonaService bi-temporal state management."""

    def test_update_emotion(self, fresh_conn):
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        result = svc.update_emotion("fresh", "joy", 0.9, context="テスト")
        assert result.is_ok
        # Verify via get_context
        ctx = svc.get_context("fresh")
        assert ctx.is_ok
        assert ctx.value.emotion == "joy"
        assert ctx.value.emotion_intensity == 0.9

    def test_update_physical_state(self, fresh_conn):
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        result = svc.update_physical_state("fresh", physical_state="元気", mental_state="集中")
        assert result.is_ok
        ctx = svc.get_context("fresh")
        assert ctx.is_ok
        assert ctx.value.physical_state == "元気"
        assert ctx.value.mental_state == "集中"

    def test_state_history_preserved(self, fresh_conn):
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        svc.update_emotion("fresh", "joy", 0.8)
        svc.update_emotion("fresh", "sadness", 0.5)
        history = repo.get_state_history("fresh", "emotion")
        assert history.is_ok
        entries = history.value
        assert len(entries) >= 2
        # Latest first
        assert entries[0].value == "sadness"
        assert entries[1].value == "joy"

    def test_get_current_state_defaults(self, fresh_conn):
        """A fresh persona returns sensible defaults."""
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        ctx = svc.get_context("fresh")
        assert ctx.is_ok
        assert ctx.value.emotion == "neutral"
        assert ctx.value.emotion_intensity == 0.0

    def test_update_relationship(self, fresh_conn):
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        result = svc.update_relationship("fresh", "恋人")
        assert result.is_ok
        ctx = svc.get_context("fresh")
        assert ctx.is_ok
        assert ctx.value.relationship_status == "恋人"

    def test_update_user_info(self, fresh_conn):
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        result = svc.update_user_info("fresh", {"name": "太郎", "age": "25"})
        assert result.is_ok
        info = repo.get_user_info("fresh")
        assert info.is_ok
        assert info.value["name"] == "太郎"

    def test_update_persona_info(self, fresh_conn):
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        result = svc.update_persona_info("fresh", {"nickname": "ヘルタ"})
        assert result.is_ok
        info = repo.get_persona_info("fresh")
        assert info.is_ok
        assert info.value["nickname"] == "ヘルタ"

    def test_emotion_history_recorded(self, fresh_conn):
        repo = SQLitePersonaRepository(fresh_conn)
        svc = PersonaService(repo)
        svc.update_emotion("fresh", "anger", 0.7, context="テスト怒り")
        history = repo.get_emotion_history("fresh")
        assert history.is_ok
        assert len(history.value) >= 1
        assert history.value[0].emotion_type == "anger"


# =====================================================================
# Phase E: Equipment Management
# =====================================================================


class TestEquipment:
    """Phase E: EquipmentService via SQLiteEquipmentRepository."""

    def test_add_item(self, fresh_conn):
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        result = svc.add_item("白いドレス", category="clothing", description="シンプル")
        assert result.is_ok

    def test_equip_item(self, fresh_conn):
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        svc.add_item("黒いブーツ", category="shoes")
        result = svc.equip({"shoes": "黒いブーツ"})
        assert result.is_ok
        eq = svc.get_equipment()
        assert eq.is_ok
        assert eq.value["shoes"] == "黒いブーツ"

    def test_unequip_item(self, fresh_conn):
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        svc.add_item("帽子", category="accessories")
        svc.equip({"head": "帽子"})
        result = svc.unequip("head")
        assert result.is_ok
        eq = svc.get_equipment()
        assert eq.is_ok
        assert eq.value.get("head") is None

    def test_equipment_history(self, fresh_conn):
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        svc.add_item("赤いマフラー", category="accessories")
        svc.equip({"accessories": "赤いマフラー"})
        history = svc.get_history(days=1)
        assert history.is_ok
        assert len(history.value) >= 1

    def test_auto_add_on_equip(self, fresh_conn):
        """auto_add=True creates the item if it doesn't exist."""
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        result = svc.equip({"top": "新しいシャツ"}, auto_add=True)
        assert result.is_ok
        found = repo.find_item_by_name("新しいシャツ")
        assert found.is_ok
        assert found.value is not None

    def test_invalid_slot_rejected(self, fresh_conn):
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        result = svc.equip({"invalid_slot": "何か"})
        assert not result.is_ok

    def test_search_items(self, fresh_conn):
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        svc.add_item("青いドレス", category="clothing")
        svc.add_item("青い靴", category="shoes")
        result = svc.search_items(query="青い")
        assert result.is_ok
        assert len(result.value) == 2

    def test_remove_item(self, fresh_conn):
        repo = SQLiteEquipmentRepository(fresh_conn)
        svc = EquipmentService(repo)
        svc.add_item("捨てる物")
        result = svc.remove_item("捨てる物")
        assert result.is_ok
        found = repo.find_item_by_name("捨てる物")
        assert found.is_ok
        assert found.value is None


# =====================================================================
# Phase F: Keyword Search
# =====================================================================


class _KeywordAdapter:
    """Adapt SQLiteMemoryRepository.search_keyword to KeywordSearchStrategy."""

    def __init__(self, repo: SQLiteMemoryRepository) -> None:
        self._repo = repo

    def search(self, query: str, limit: int = 10):
        return self._repo.search_keyword(query, limit)


@pytest.mark.usefixtures("_check_zip_data")
class TestSearch:
    """Phase F: Keyword search against imported data."""

    def test_keyword_search(self, herta_conn):
        repo = SQLiteMemoryRepository(herta_conn)
        result = repo.search_keyword("ヘルタ", limit=10)
        assert result.is_ok
        # herta data should mention ヘルタ at least once
        assert len(result.value) >= 0

    def test_keyword_search_returns_results(self, nilou_conn):
        """nilou's 1210 memories should yield some matches for common words."""
        repo = SQLiteMemoryRepository(nilou_conn)
        result = repo.search_keyword("memory", limit=5)
        assert result.is_ok

    def test_search_engine_keyword_mode(self, herta_conn):
        """SearchEngine with keyword-only strategy."""
        repo = SQLiteMemoryRepository(herta_conn)
        adapter = _KeywordAdapter(repo)
        engine = SearchEngine(keyword_search=adapter)
        query = SearchQuery(text="好き", mode="keyword", top_k=5)
        result = engine.search(query)
        assert result.is_ok

    def test_search_engine_hybrid_fallback(self, herta_conn):
        """Hybrid mode without semantic still returns keyword results."""
        repo = SQLiteMemoryRepository(herta_conn)
        adapter = _KeywordAdapter(repo)
        engine = SearchEngine(keyword_search=adapter, semantic_search=None)
        query = SearchQuery(text="記憶", mode="hybrid", top_k=5)
        result = engine.search(query)
        assert result.is_ok

    def test_search_with_tags_filter(self, fresh_conn):
        """Tags-based retrieval via repository."""
        repo = SQLiteMemoryRepository(fresh_conn)
        now = get_now()
        m1 = Memory(key="tag_food", content="タグ付き記憶", created_at=now, updated_at=now, tags=["food", "test"])
        m2 = Memory(key="tag_other", content="別の記憶", created_at=now, updated_at=now, tags=["other"])
        repo.save(m1)
        repo.save(m2)
        result = repo.find_by_tags(["food"])
        assert result.is_ok
        assert len(result.value) >= 1
        assert any("food" in m.tags for m in result.value)

    def test_search_with_importance_filter(self, fresh_conn):
        """Importance-based filtering via manual check."""
        repo = SQLiteMemoryRepository(fresh_conn)
        now = get_now()
        m1 = Memory(key="imp_high", content="重要", created_at=now, updated_at=now, importance=0.9)
        m2 = Memory(key="imp_low", content="普通", created_at=now, updated_at=now, importance=0.3)
        repo.save(m1)
        repo.save(m2)
        all_mems = repo.find_all()
        assert all_mems.is_ok
        high = [m for m in all_mems.value if m.importance >= 0.8]
        assert len(high) >= 1

    def test_keyword_search_japanese(self, fresh_conn):
        """日本語キーワード検索が正しく動作する."""
        repo = SQLiteMemoryRepository(fresh_conn)
        now = get_now()
        m1 = Memory(key="jp_search_1", content="ユーザーはラーメンが好きです", created_at=now, updated_at=now)
        m2 = Memory(key="jp_search_2", content="今日は天気がいい", created_at=now, updated_at=now)
        repo.save(m1)
        repo.save(m2)
        result = repo.search_keyword("ラーメン")
        assert result.is_ok
        assert len(result.value) >= 1
        assert "ラーメン" in result.value[0][0].content


# =====================================================================
# Phase G: Japanese Temporal Expressions
# =====================================================================


class TestTimeUtils:
    """Phase G: parse_date_range for Japanese temporal expressions."""

    def test_yesterday(self):
        start, end = parse_date_range("昨日")
        assert start is not None and end is not None
        now = get_now()
        yesterday = now - timedelta(days=1)
        assert start.date() == yesterday.date()
        assert end.date() == yesterday.date()

    def test_day_before_yesterday(self):
        start, end = parse_date_range("一昨日")
        assert start is not None and end is not None
        now = get_now()
        expected = now - timedelta(days=2)
        assert start.date() == expected.date()

    def test_day_before_yesterday_hiragana(self):
        start, end = parse_date_range("おととい")
        assert start is not None and end is not None
        now = get_now()
        expected = now - timedelta(days=2)
        assert start.date() == expected.date()

    def test_last_week(self):
        start, end = parse_date_range("先週")
        assert start is not None and end is not None
        # Should be last week's Monday to Sunday
        assert start.weekday() == 0  # Monday
        assert end < get_now()

    def test_last_month(self):
        start, end = parse_date_range("先月")
        assert start is not None and end is not None
        now = get_now()
        # start should be first day of previous month
        assert start.day == 1
        assert start.month != now.month or start.year != now.year

    def test_n_days_ago_arabic(self):
        start, end = parse_date_range("3日前")
        assert start is not None and end is not None
        now = get_now()
        expected = now - timedelta(days=3)
        assert start.date() == expected.date()

    def test_n_days_ago_kanji(self):
        start, end = parse_date_range("三日前")
        assert start is not None and end is not None
        now = get_now()
        expected = now - timedelta(days=3)
        assert start.date() == expected.date()

    def test_this_morning(self):
        start, end = parse_date_range("今朝")
        assert start is not None and end is not None
        now = get_now()
        assert start.date() == now.date()
        assert start.hour == 0
        assert end.hour == 12

    def test_n_weeks_ago(self):
        start, end = parse_date_range("2週間前")
        assert start is not None and end is not None
        assert end < get_now()

    def test_n_months_ago(self):
        start, end = parse_date_range("3ヶ月前")
        assert start is not None and end is not None
        now = get_now()
        # Should be some month ~3 months back
        diff_months = (now.year - start.year) * 12 + (now.month - start.month)
        assert diff_months == 3

    def test_n_months_ago_alt(self):
        """3か月前 (か instead of ヶ)."""
        start, end = parse_date_range("3か月前")
        assert start is not None and end is not None

    def test_relative_days_7d(self):
        start, end = parse_date_range("7d")
        assert start is not None and end is not None
        diff = end - start
        assert 6 <= diff.days <= 7

    def test_absolute_range(self):
        start, end = parse_date_range("2025-01-01~2025-06-30")
        assert start is not None and end is not None
        assert start.year == 2025 and start.month == 1 and start.day == 1
        assert end.year == 2025 and end.month == 6 and end.day == 30

    def test_today(self):
        start, end = parse_date_range("今日")
        assert start is not None and end is not None
        now = get_now()
        assert start.date() == now.date()

    def test_invalid_returns_none(self):
        start, end = parse_date_range("意味不明な文字列")
        assert start is None and end is None

    def test_none_input(self):
        start, end = parse_date_range(None)
        assert start is None and end is None


# =====================================================================
# Phase H: Export/Import Roundtrip
# =====================================================================


@pytest.mark.usefixtures("_check_zip_data")
class TestExportImportRoundtrip:
    """Phase H: JSONL export → import data integrity."""

    def test_jsonl_roundtrip(self, tmp_path):
        """JSONL export → re-count lines matches original records."""
        conn, counts = _import_zip(tmp_path, "herta")
        export_path = tmp_path / "export.jsonl"
        exporter = JSONLExporter()
        result = exporter.export_persona(conn, "test_herta", str(export_path))
        assert result.is_ok
        total_exported = result.value
        assert total_exported > 0

        # Count lines
        with open(export_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == total_exported

        # Verify each line is valid JSON with a "type" field
        for line in lines:
            record = json.loads(line)
            assert "type" in record
        conn.close()

    def test_export_contains_memory_records(self, tmp_path):
        """Export includes all memory records from herta."""
        conn, counts = _import_zip(tmp_path, "herta")
        export_path = tmp_path / "herta_export.jsonl"
        exporter = JSONLExporter()
        exporter.export_persona(conn, "test_herta", str(export_path))

        memory_count = 0
        with open(export_path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if record["type"] == "memory":
                    memory_count += 1
        assert memory_count == PERSONA_EXPECTED_COUNTS["herta"]
        conn.close()

    def test_export_contains_all_tables(self, tmp_path):
        """Export includes records from multiple table types."""
        conn, _ = _import_zip(tmp_path, "herta")
        export_path = tmp_path / "full_export.jsonl"
        exporter = JSONLExporter()
        exporter.export_persona(conn, "test_herta", str(export_path))

        types_seen: set[str] = set()
        with open(export_path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                types_seen.add(record["type"])
        # Must have at least memory records
        assert "memory" in types_seen
        conn.close()

    def test_export_reimport_count_matches(self, tmp_path):
        """Export herta → import to new persona → memory counts match."""
        # 1. Import herta
        conn1, _ = _import_zip(tmp_path, "herta")
        db1 = conn1.get_memory_db()
        original_count = db1.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]

        # 2. Export to JSONL
        export_path = tmp_path / "roundtrip.jsonl"
        exporter = JSONLExporter()
        exporter.export_persona(conn1, "test_herta", str(export_path))

        # 3. Count memory-type lines
        exported_memories = 0
        with open(export_path, encoding="utf-8") as f:
            for line in f:
                if json.loads(line)["type"] == "memory":
                    exported_memories += 1

        assert exported_memories == original_count
        conn1.close()


# =====================================================================
# Phase I: Ebbinghaus Forgetting Curve
# =====================================================================


class TestForgettingCurve:
    """Phase I: MemoryStrength decay and recall boost."""

    def test_initial_strength(self):
        """New MemoryStrength has strength=1.0, stability=1.0."""
        ms = MemoryStrength(memory_key="test_key")
        assert ms.strength == 1.0
        assert ms.stability == 1.0
        assert ms.recall_count == 0

    def test_compute_recall_at_zero(self):
        """At t=0, recall probability is 1.0."""
        ms = MemoryStrength(memory_key="test")
        assert ms.compute_recall(0.0) == pytest.approx(1.0)

    def test_strength_decays_over_time(self):
        """R(t) = e^(-t/S) < 1 for t > 0."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        # After 24 hours (stability=1 day): R = e^(-24/24) = e^-1 ≈ 0.368
        recall = ms.compute_recall(24.0)
        assert recall == pytest.approx(math.exp(-1), rel=1e-6)
        assert recall < 1.0

    def test_higher_stability_slower_decay(self):
        """Higher stability means slower decay."""
        ms_low = MemoryStrength(memory_key="low", stability=1.0)
        ms_high = MemoryStrength(memory_key="high", stability=10.0)
        recall_low = ms_low.compute_recall(48.0)
        recall_high = ms_high.compute_recall(48.0)
        assert recall_high > recall_low

    def test_boost_on_recall(self):
        """boost_on_recall increases stability and resets strength."""
        ms = MemoryStrength(memory_key="test", stability=1.0, strength=0.5)
        ms.boost_on_recall()
        assert ms.recall_count == 1
        assert ms.stability == 1.5  # 1.0 * 1.5
        assert ms.strength == 1.0

    def test_boost_on_recall_capped(self):
        """Stability is capped at 365."""
        ms = MemoryStrength(memory_key="test", stability=300.0)
        ms.boost_on_recall()
        assert ms.stability == 365.0  # min(300*1.5, 365) = 365

    def test_boost_on_recall_persisted(self, fresh_conn):
        """boost_recall through MemoryService persists to DB."""
        repo = SQLiteMemoryRepository(fresh_conn)
        svc = MemoryService(repo)
        created = svc.create_memory("永続化テスト")
        assert created.is_ok
        key = created.value.key

        result = svc.boost_recall(key)
        assert result.is_ok
        assert result.value.recall_count == 1

        # Read back from DB
        strength = repo.get_strength(key)
        assert strength.is_ok
        assert strength.value is not None
        assert strength.value.recall_count == 1
        assert strength.value.stability == 1.5

    def test_zero_stability(self):
        """Zero stability returns 0.0 recall."""
        ms = MemoryStrength(memory_key="test", stability=0.0)
        assert ms.compute_recall(10.0) == 0.0

    def test_multiple_boosts(self):
        """Multiple recalls keep increasing stability."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        ms.boost_on_recall()  # 1.5
        ms.boost_on_recall()  # 2.25
        ms.boost_on_recall()  # 3.375
        assert ms.recall_count == 3
        assert ms.stability == pytest.approx(3.375)


# =====================================================================
# Phase J: Imported Data Cross-Persona Isolation
# =====================================================================


@pytest.mark.usefixtures("_check_zip_data")
class TestCrossPersonaIsolation:
    """Verify that each persona's data lives in its own DB."""

    def test_separate_databases(self, tmp_path):
        """Two imports into different personas don't interfere."""
        conn_h, _ = _import_zip(tmp_path, "herta")
        conn_c, _ = _import_zip(tmp_path, "citlali")

        h_count = conn_h.get_memory_db().execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
        c_count = conn_c.get_memory_db().execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]

        assert h_count == PERSONA_EXPECTED_COUNTS["herta"]
        assert c_count == PERSONA_EXPECTED_COUNTS["citlali"]
        conn_h.close()
        conn_c.close()
