from __future__ import annotations


def upgrade(db) -> None:
    """Add image_gen columns to chat_settings."""
    db.execute("ALTER TABLE chat_settings ADD COLUMN image_gen_enabled BOOLEAN DEFAULT 0")
    db.execute("ALTER TABLE chat_settings ADD COLUMN image_gen_provider TEXT DEFAULT 'openai'")
    db.execute("ALTER TABLE chat_settings ADD COLUMN image_gen_dalle_model TEXT DEFAULT 'dall-e-3'")
    db.execute("ALTER TABLE chat_settings ADD COLUMN image_gen_stability_url TEXT DEFAULT ''")
    db.commit()
