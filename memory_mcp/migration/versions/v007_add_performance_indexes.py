"""Migration v007: Add performance indexes to prevent full table scans."""

from __future__ import annotations

VERSION = "007"
DESCRIPTION = "Add performance indexes on memories, memory_strength, and emotion_history"


def upgrade(db) -> None:
    """Create missing indexes."""
    db.executescript("""\
CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_strength_strength ON memory_strength(strength);
CREATE INDEX IF NOT EXISTS idx_emotion_history_persona ON emotion_history(timestamp DESC);
""")


def downgrade(db) -> None:
    """Drop performance indexes."""
    db.executescript("""\
DROP INDEX IF EXISTS idx_memories_updated_at;
DROP INDEX IF EXISTS idx_memories_created_at;
DROP INDEX IF EXISTS idx_memory_strength_strength;
DROP INDEX IF EXISTS idx_emotion_history_persona;
""")
