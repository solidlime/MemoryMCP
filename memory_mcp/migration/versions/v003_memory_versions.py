from __future__ import annotations


def upgrade(db) -> None:
    """Add memory_versions table for version tracking."""
    db.executescript(
        """\
CREATE TABLE IF NOT EXISTS memory_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_key TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    content TEXT NOT NULL,
    metadata TEXT,
    changed_by TEXT DEFAULT 'user',
    change_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(memory_key, version)
);
CREATE INDEX IF NOT EXISTS idx_memory_versions_key ON memory_versions(memory_key);
"""
    )


def downgrade(db) -> None:
    """Remove memory_versions table."""
    db.execute("DROP TABLE IF EXISTS memory_versions")
