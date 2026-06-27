"""Unit tests for migration v009: goals/promises → memories."""

from __future__ import annotations

import json
import sqlite3

from nous.migration.versions.v006_normalize_emotions import upgrade as upgrade_v006
from nous.migration.versions.v008_add_persona_to_goals_promises import upgrade as upgrade_v008


def _make_db():
    """Create an in-memory SQLite DB with the minimal schema for v009."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            key TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            importance REAL DEFAULT 0.5,
            emotion TEXT DEFAULT 'neutral',
            emotion_intensity REAL DEFAULT 0.0,
            physical_state TEXT,
            mental_state TEXT,
            environment TEXT,
            relationship_status TEXT,
            action_tag TEXT,
            source_context TEXT,
            related_keys TEXT DEFAULT '[]',
            summary_ref TEXT,
            equipped_items TEXT,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            privacy_level TEXT DEFAULT 'internal'
        );

        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS promises (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            fulfilled_at TEXT,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS persona_info (
            persona TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (persona, key)
        );
    """)
    conn.commit()
    return conn


def _run_upgrade(conn):
    from nous.migration.versions.v009_goals_promises_to_memories import upgrade

    upgrade(conn)


class TestV009Migration:
    def test_active_goal_migrated_with_active_tag(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g1", "Learn Python", "active", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%goal%'").fetchall()
        assert len(rows) == 1
        tags = json.loads(rows[0]["tags"])
        assert "goal" in tags
        assert "active" in tags

    def test_completed_goal_migrated_with_achieved_tag(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g2", "Finish project", "completed", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%goal%'").fetchall()
        assert len(rows) == 1
        tags = json.loads(rows[0]["tags"])
        assert "achieved" in tags

    def test_done_goal_migrated_with_achieved_tag(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g3", "Done goal", "done", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%achieved%'").fetchall()
        assert len(rows) == 1

    def test_other_status_goal_migrated_as_cancelled(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g4", "Abandoned goal", "paused", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%cancelled%'").fetchall()
        assert len(rows) == 1

    def test_active_promise_migrated(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO promises (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("p1", "Keep secret", "active", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%promise%'").fetchall()
        assert len(rows) == 1
        tags = json.loads(rows[0]["tags"])
        assert "promise" in tags
        assert "active" in tags

    def test_fulfilled_promise_migrated(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO promises (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("p2", "Completed promise", "fulfilled", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%fulfilled%'").fetchall()
        assert len(rows) == 1

    def test_done_promise_migrated_as_fulfilled(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO promises (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("p3", "Done promise", "done", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%fulfilled%'").fetchall()
        assert len(rows) == 1

    def test_goals_table_dropped_after_migration(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g1", "Some goal", "active", now, now),
        )
        db.commit()

        _run_upgrade(db)

        # goals table should no longer exist
        result = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='goals'").fetchone()
        assert result is None

    def test_promises_table_dropped_after_migration(self):
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO promises (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("p1", "Some promise", "active", now, now),
        )
        db.commit()

        _run_upgrade(db)

        result = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='promises'").fetchone()
        assert result is None

    def test_empty_goals_and_promises(self):
        """Migration on empty tables should complete without error."""
        db = _make_db()
        _run_upgrade(db)  # Should not raise

        mem_count = db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        assert mem_count == 0

    def test_no_duplicate_on_second_run(self):
        """Running upgrade twice should not duplicate memories."""
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g1", "Idempotent goal", "active", now, now),
        )
        db.commit()

        _run_upgrade(db)
        # Re-create goals table and run again to test idempotency
        db.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g1", "Idempotent goal", "active", now, now),
        )
        db.commit()
        _run_upgrade(db)

        # Memory should only exist once
        rows = db.execute("SELECT * FROM memories WHERE content = 'Idempotent goal'").fetchall()
        assert len(rows) == 1

    def test_persona_info_goals_keys_deleted(self):
        """persona_info entries for goals/promises should be removed."""
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO persona_info (persona, key, value, updated_at) VALUES (?,?,?,?)",
            ("test", "goals", '["goal1"]', now),
        )
        db.execute(
            "INSERT INTO persona_info (persona, key, value, updated_at) VALUES (?,?,?,?)",
            ("test", "promises", '["promise1"]', now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM persona_info WHERE key IN ('goals', 'promises')").fetchall()
        assert len(rows) == 0

    def test_migration_without_goals_table(self):
        """If goals table doesn't exist, migration should not fail."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                emotion TEXT DEFAULT 'neutral',
                emotion_intensity REAL DEFAULT 0.0,
                physical_state TEXT,
                mental_state TEXT,
                environment TEXT,
                relationship_status TEXT,
                action_tag TEXT,
                source_context TEXT,
                related_keys TEXT DEFAULT '[]',
                summary_ref TEXT,
                equipped_items TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                privacy_level TEXT DEFAULT 'internal'
            );
        """)
        conn.commit()

        # Should not raise even though goals/promises tables don't exist
        _run_upgrade(conn)

    def test_cancelled_promise_status(self):
        """Promises with status other than active/fulfilled/done are tagged 'cancelled'."""
        db = _make_db()
        now = "2025-01-01T00:00:00"
        db.execute(
            "INSERT INTO promises (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("p4", "Abandoned promise", "paused", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE tags LIKE '%promise%'").fetchall()
        assert len(rows) == 1
        tags = json.loads(rows[0]["tags"])
        assert "cancelled" in tags

    def test_goal_skip_when_key_already_exists(self):
        """Goal migration skips inserting if memory key already exists."""
        import hashlib

        db = _make_db()
        now = "2025-01-01T00:00:00"
        description = "Pre-existing goal"
        key = f"goal_{hashlib.md5(description.encode()).hexdigest()[:12]}"

        # Pre-insert the memory with that key
        db.execute(
            "INSERT INTO memories (key, content, created_at, updated_at) VALUES (?,?,?,?)",
            (key, "already there", now, now),
        )
        db.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g_dup", description, "active", now, now),
        )
        db.commit()

        _run_upgrade(db)

        # Should still be 1 row (not duplicated)
        rows = db.execute("SELECT * FROM memories WHERE key = ?", (key,)).fetchall()
        assert len(rows) == 1

    def test_promise_skip_when_key_already_exists(self):
        """Promise migration skips inserting if memory key already exists."""
        import hashlib

        db = _make_db()
        now = "2025-01-01T00:00:00"
        description = "Pre-existing promise"
        key = f"promise_{hashlib.md5(description.encode()).hexdigest()[:12]}"

        db.execute(
            "INSERT INTO memories (key, content, created_at, updated_at) VALUES (?,?,?,?)",
            (key, "already there", now, now),
        )
        db.execute(
            "INSERT INTO promises (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("p_dup", description, "active", now, now),
        )
        db.commit()

        _run_upgrade(db)

        rows = db.execute("SELECT * FROM memories WHERE key = ?", (key,)).fetchall()
        assert len(rows) == 1

    def test_goal_tuple_row_fallback(self):
        """Migration handles tuple rows (no row_factory=sqlite3.Row) via fallback."""
        # Create a DB without sqlite3.Row row_factory so rows come back as tuples
        conn = sqlite3.connect(":memory:")
        # No row_factory set — rows will be plain tuples
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                emotion TEXT DEFAULT 'neutral',
                emotion_intensity REAL DEFAULT 0.0,
                physical_state TEXT,
                mental_state TEXT,
                environment TEXT,
                relationship_status TEXT,
                action_tag TEXT,
                source_context TEXT,
                related_keys TEXT DEFAULT '[]',
                summary_ref TEXT,
                equipped_items TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                privacy_level TEXT DEFAULT 'internal'
            );
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                priority INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS promises (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                priority INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS persona_info (
                persona TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (persona, key)
            );
        """)
        conn.commit()

        now = "2025-01-01T00:00:00"
        conn.execute(
            "INSERT INTO goals (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("g_tuple", "Tuple row goal", "active", now, now),
        )
        conn.execute(
            "INSERT INTO promises (id, description, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            ("p_tuple", "Tuple row promise", "fulfilled", now, now),
        )
        conn.commit()

        _run_upgrade(conn)

        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        assert count == 2


# ====== From test_migration_v006.py ======


def _create_test_db() -> sqlite3.Connection:
    """Create an in-memory SQLite DB with the memories table."""
    db = sqlite3.connect(":memory:")
    db.execute(
        """
        CREATE TABLE memories (
            key TEXT PRIMARY KEY,
            content TEXT,
            emotion TEXT
        )
        """
    )
    return db


def test_upgrade_normalizes_emotions():
    """Non-canonical emotion values are normalized after upgrade."""
    db = _create_test_db()
    db.executemany(
        "INSERT INTO memories (key, content, emotion) VALUES (?, ?, ?)",
        [
            ("m001", "happy memory", "happy"),  # → joy
            ("m002", "sad memory", "sad"),  # → sadness
            ("m003", "angry memory", "angry"),  # → anger
            ("m004", "love memory", "愛情"),  # → love
            ("m005", "curious memory", "curious"),  # → curiosity
        ],
    )

    upgrade_v006(db)

    rows = {r[0]: r[1] for r in db.execute("SELECT key, emotion FROM memories").fetchall()}
    assert rows["m001"] == "joy"
    assert rows["m002"] == "sadness"
    assert rows["m003"] == "anger"
    assert rows["m004"] == "love"
    assert rows["m005"] == "curiosity"


def test_upgrade_already_canonical_unchanged():
    """Rows with already-canonical emotion are not updated."""
    db = _create_test_db()
    db.executemany(
        "INSERT INTO memories (key, content, emotion) VALUES (?, ?, ?)",
        [
            ("m010", "joy memory", "joy"),
            ("m011", "neutral memory", "neutral"),
            ("m012", "sadness memory", "sadness"),
        ],
    )

    # Use total_changes to confirm no rows were touched
    before = db.total_changes
    upgrade_v006(db)
    after = db.total_changes

    assert after == before, "No UPDATE should be issued for already-canonical values"

    rows = {r[0]: r[1] for r in db.execute("SELECT key, emotion FROM memories").fetchall()}
    assert rows["m010"] == "joy"
    assert rows["m011"] == "neutral"
    assert rows["m012"] == "sadness"


def test_upgrade_null_emotion_unchanged():
    """Rows with NULL emotion are not touched."""
    db = _create_test_db()
    db.execute(
        "INSERT INTO memories (key, content, emotion) VALUES (?, ?, ?)",
        ("m020", "no emotion", None),
    )

    upgrade_v006(db)

    row = db.execute("SELECT emotion FROM memories WHERE key = 'm020'").fetchone()
    assert row[0] is None


def test_upgrade_unrecognized_emotion_becomes_neutral():
    """Unrecognized emotion is normalized to 'neutral'."""
    db = _create_test_db()
    db.execute(
        "INSERT INTO memories (key, content, emotion) VALUES (?, ?, ?)",
        ("m030", "weird emotion", "xyzunknown"),
    )

    upgrade_v006(db)

    row = db.execute("SELECT emotion FROM memories WHERE key = 'm030'").fetchone()
    assert row[0] == "neutral"


def test_upgrade_empty_table():
    """Migration on an empty table does not raise."""
    db = _create_test_db()
    upgrade_v006(db)  # Should not raise


# ====== From test_migration_v008.py ======


def _base_schema(conn: sqlite3.Connection) -> None:
    """Create goals and promises tables WITHOUT persona column."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS promises (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()


def _make_goals_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _base_schema(conn)
    conn.execute(
        "INSERT INTO goals (id, description, created_at, updated_at) VALUES ('g1', 'test', '2024-01-01', '2024-01-01')"
    )
    conn.commit()
    return conn


def _make_promises_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _base_schema(conn)
    return conn


def test_v008_adds_persona_column_to_goals():
    """v008 は goals テーブルに persona カラムを追加する。"""
    conn = _make_goals_db()
    # goals のみ存在する DB（promises なし）でも goals だけ処理される
    upgrade_v008(conn)
    conn.commit()

    cols = [row[1] for row in conn.execute("PRAGMA table_info(goals)").fetchall()]
    assert "persona" in cols

    # マイグレーション後、既存行は DEFAULT 'default' を持つ（歴史的挙動）
    row = conn.execute("SELECT persona FROM goals WHERE id='g1'").fetchone()
    assert row["persona"] == "default"
    # 明示的に persona 値を指定すると反映される
    conn.execute("UPDATE goals SET persona='test_user' WHERE id='g1'")
    row = conn.execute("SELECT persona FROM goals WHERE id='g1'").fetchone()
    assert row["persona"] == "test_user"


def test_v008_adds_persona_column_to_promises():
    """v008 は promises テーブルに persona カラムを追加する。"""
    conn = _make_promises_db()
    upgrade_v008(conn)
    conn.commit()

    cols = [row[1] for row in conn.execute("PRAGMA table_info(promises)").fetchall()]
    assert "persona" in cols


def test_v008_idempotent():
    """v008 は2回実行しても安全（idempotent）。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE goals (id TEXT PRIMARY KEY, description TEXT NOT NULL, "
        "status TEXT, priority INTEGER, persona TEXT DEFAULT 'test_user', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE promises (id TEXT PRIMARY KEY, description TEXT NOT NULL, "
        "status TEXT, priority INTEGER, persona TEXT DEFAULT 'test_user', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.commit()

    upgrade_v008(conn)
    upgrade_v008(conn)  # 2回目もエラーなし


def test_v008_new_rows_get_default_persona():
    """v008 適用後に挿入した行は persona 値を保持する。"""
    conn = _make_goals_db()
    upgrade_v008(conn)
    conn.commit()

    # 明示的に persona 値を指定して挿入
    conn.execute(
        "INSERT INTO goals (id, description, persona, created_at, updated_at) VALUES ('g2', 'new', 'test_user', '2024-01-02', '2024-01-02')"
    )
    conn.commit()

    row = conn.execute("SELECT persona FROM goals WHERE id='g2'").fetchone()
    assert row["persona"] == "test_user"
