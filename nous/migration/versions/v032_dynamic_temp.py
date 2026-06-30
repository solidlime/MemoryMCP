from __future__ import annotations

from contextlib import suppress


def upgrade(db) -> None:
    """Add dynamic temperature and top_p columns to chat_settings.

    New columns:
    - dynamic_temperature INTEGER DEFAULT 1: enable/disable dynamic temperature scaling
    - emotion_temperature_scale REAL DEFAULT 0.2: emotion influence on temperature [0.0, 1.0]
    - top_p REAL (nullable): nucleus sampling parameter, None = use provider default
    """
    with suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN dynamic_temperature INTEGER DEFAULT 1")
    with suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN emotion_temperature_scale REAL DEFAULT 0.2")
    with suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN top_p REAL")

    db.commit()
