from __future__ import annotations

import contextlib


def upgrade(db) -> None:
    """Add reflection and retrieval weight settings to chat_settings."""
    # Reflection settings
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN reflection_enabled INTEGER DEFAULT 1")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN reflection_threshold REAL DEFAULT 3.0")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN reflection_min_interval_hours REAL DEFAULT 1.0")
    # Session summarization
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN session_summarize INTEGER DEFAULT 1")
    # Retrieval weights
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN retrieval_recency_weight REAL DEFAULT 0.3")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN retrieval_importance_weight REAL DEFAULT 0.3")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN retrieval_relevance_weight REAL DEFAULT 0.4")
    db.commit()
