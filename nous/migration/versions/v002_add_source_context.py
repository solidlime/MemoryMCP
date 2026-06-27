from __future__ import annotations


def upgrade(db) -> None:
    """Add ``source_context`` column to the memories table.

    Legacy databases created before v2 lack this column.  The migration is
    idempotent — it checks ``PRAGMA table_info`` first.
    """
    columns = [row[1] for row in db.execute("PRAGMA table_info(memories)").fetchall()]
    if "source_context" not in columns:
        db.execute("ALTER TABLE memories ADD COLUMN source_context TEXT")
