from __future__ import annotations


def upgrade(db) -> None:
    """Add session_events table for context-mode style recording."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            persona TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id, timestamp)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_session_events_persona ON session_events(persona, timestamp)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_session_events_type ON session_events(event_type, timestamp)")
    db.commit()
