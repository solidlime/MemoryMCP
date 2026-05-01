from __future__ import annotations
import contextlib


def upgrade(db) -> None:
    """Add sandbox_enabled to chat_settings."""
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN sandbox_enabled INTEGER DEFAULT 0")
    db.commit()
