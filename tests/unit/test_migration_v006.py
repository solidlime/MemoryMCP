"""Unit tests for migration v006: normalize emotion_type values."""

from __future__ import annotations

import sqlite3

from memory_mcp.migration.versions.v006_normalize_emotions import upgrade


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

    upgrade(db)

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
    upgrade(db)
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

    upgrade(db)

    row = db.execute("SELECT emotion FROM memories WHERE key = 'm020'").fetchone()
    assert row[0] is None


def test_upgrade_unrecognized_emotion_becomes_neutral():
    """Unrecognized emotion is normalized to 'neutral'."""
    db = _create_test_db()
    db.execute(
        "INSERT INTO memories (key, content, emotion) VALUES (?, ?, ?)",
        ("m030", "weird emotion", "xyzunknown"),
    )

    upgrade(db)

    row = db.execute("SELECT emotion FROM memories WHERE key = 'm030'").fetchone()
    assert row[0] == "neutral"


def test_upgrade_empty_table():
    """Migration on an empty table does not raise."""
    db = _create_test_db()
    upgrade(db)  # Should not raise
