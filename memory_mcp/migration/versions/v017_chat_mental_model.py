from __future__ import annotations
import contextlib


def upgrade(db) -> None:
    """Add mental_model_enabled and mental_model_min_samples to chat_settings."""
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN mental_model_enabled INTEGER DEFAULT 1")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN mental_model_min_samples INTEGER DEFAULT 3")
    db.commit()
