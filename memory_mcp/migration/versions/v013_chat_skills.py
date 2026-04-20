from __future__ import annotations

import contextlib


def upgrade(db) -> None:
    """Add skills table and enabled_skills column to chat_settings."""
    with contextlib.suppress(Exception):
        db.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                content     TEXT NOT NULL DEFAULT '',
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN enabled_skills TEXT DEFAULT '[]'")
    db.commit()
