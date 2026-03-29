"""Performance benchmarks for SQLite memory operations."""

import sqlite3


def _setup_db(n: int) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE memories (
        key TEXT PRIMARY KEY,
        content TEXT,
        tags TEXT DEFAULT '[]',
        importance REAL DEFAULT 0.5,
        emotion TEXT DEFAULT 'neutral',
        emotion_intensity REAL DEFAULT 0.0,
        created_at TEXT,
        updated_at TEXT
    )""")
    db.executemany(
        "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                f"key_{i}",
                f"テスト記憶 {i} Python 機械学習 ユーザー",
                "[]",
                0.5,
                "neutral",
                0.0,
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
            )
            for i in range(n)
        ],
    )
    db.commit()
    return db


def test_keyword_search_sqlite_500(benchmark):
    """Benchmark SQLite LIKE keyword search across 500 memories."""
    db = _setup_db(500)

    def search_keyword():
        return db.execute(
            "SELECT key, content FROM memories WHERE content LIKE ? LIMIT 10",
            ("%Python%",),
        ).fetchall()

    results = benchmark(search_keyword)
    assert len(results) > 0


def test_keyword_search_sqlite_1000(benchmark):
    """Benchmark SQLite LIKE keyword search across 1000 memories."""
    db = _setup_db(1000)

    def search_keyword():
        return db.execute(
            "SELECT key, content FROM memories WHERE content LIKE ? LIMIT 10",
            ("%Python%",),
        ).fetchall()

    results = benchmark(search_keyword)
    assert len(results) > 0


def test_importance_filter_500(benchmark):
    """Benchmark filtering memories by importance threshold (500 rows)."""
    db = _setup_db(500)

    def search_by_importance():
        return db.execute(
            "SELECT key, content, importance FROM memories WHERE importance >= ? ORDER BY importance DESC LIMIT 20",
            (0.7,),
        ).fetchall()

    benchmark(search_by_importance)


def test_bulk_insert_100(benchmark):
    """Benchmark bulk inserting 100 rows into SQLite."""

    def run():
        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE memories (
            key TEXT PRIMARY KEY, content TEXT, tags TEXT,
            importance REAL, emotion TEXT, emotion_intensity REAL,
            created_at TEXT, updated_at TEXT
        )""")
        db.executemany(
            "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f"key_{i}",
                    f"content {i}",
                    "[]",
                    0.5,
                    "neutral",
                    0.0,
                    "2026-01-01T00:00:00",
                    "2026-01-01T00:00:00",
                )
                for i in range(100)
            ],
        )
        db.commit()
        return db

    benchmark(run)
