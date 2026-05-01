from __future__ import annotations

import contextlib


def upgrade(db) -> None:
    """Add display_history_turns and housekeeping_threshold to chat_settings."""
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN display_history_turns INTEGER DEFAULT 20")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN housekeeping_threshold INTEGER DEFAULT 10")
    db.commit()
