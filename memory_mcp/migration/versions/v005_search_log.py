"""Migration v005: Add search_log table for topic detection."""

from __future__ import annotations

VERSION = "005"
DESCRIPTION = "Add search_log table"


def upgrade(db) -> None:
    """Create search_log table."""
    db.executescript("""\
CREATE TABLE IF NOT EXISTS search_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    mode TEXT DEFAULT 'hybrid',
    result_count INTEGER DEFAULT 0,
    searched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_search_log_time ON search_log(searched_at DESC);
""")


def downgrade(db) -> None:
    """Drop search_log table."""
    db.execute("DROP TABLE IF EXISTS search_log")
