from __future__ import annotations


def upgrade(db) -> None:
    """Add searxng_url column to chat_settings."""
    db.execute("ALTER TABLE chat_settings ADD COLUMN searxng_url TEXT DEFAULT 'http://nas:11111'")
    db.commit()
