"""Tests for migration v008: persona column in goals/promises."""
import sqlite3

from memory_mcp.migration.versions.v008_add_persona_to_goals_promises import upgrade


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
    upgrade(conn)
    conn.commit()

    cols = [row[1] for row in conn.execute("PRAGMA table_info(goals)").fetchall()]
    assert "persona" in cols

    row = conn.execute("SELECT persona FROM goals WHERE id='g1'").fetchone()
    assert row["persona"] == "default"


def test_v008_adds_persona_column_to_promises():
    """v008 は promises テーブルに persona カラムを追加する。"""
    conn = _make_promises_db()
    upgrade(conn)
    conn.commit()

    cols = [row[1] for row in conn.execute("PRAGMA table_info(promises)").fetchall()]
    assert "persona" in cols


def test_v008_idempotent():
    """v008 は2回実行しても安全（idempotent）。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE goals (id TEXT PRIMARY KEY, description TEXT NOT NULL, "
        "status TEXT, priority INTEGER, persona TEXT DEFAULT 'default', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE promises (id TEXT PRIMARY KEY, description TEXT NOT NULL, "
        "status TEXT, priority INTEGER, persona TEXT DEFAULT 'default', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.commit()

    upgrade(conn)
    upgrade(conn)  # 2回目もエラーなし


def test_v008_new_rows_get_default_persona():
    """v008 適用後に挿入した行は persona='default' を持つ。"""
    conn = _make_goals_db()
    upgrade(conn)
    conn.commit()

    conn.execute(
        "INSERT INTO goals (id, description, created_at, updated_at) VALUES ('g2', 'new', '2024-01-02', '2024-01-02')"
    )
    conn.commit()

    row = conn.execute("SELECT persona FROM goals WHERE id='g2'").fetchone()
    assert row["persona"] == "default"
