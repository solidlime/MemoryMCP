from __future__ import annotations

from contextlib import suppress


def upgrade(db) -> None:
    """Add 7-factor scoring columns to memory_strength table.

    New columns:
    - last_utility TEXT: ISO timestamp of last utility assessment
    - interference_count INTEGER DEFAULT 0: contradiction detection count
    - link_count INTEGER DEFAULT 0: number of linked related memories
    - emotion_peak REAL DEFAULT 0.0: highest emotion intensity ever recorded
    - is_ltm INTEGER DEFAULT 0: 1 = long-term memory, 0 = short-term
    """
    with suppress(Exception):
        db.execute("ALTER TABLE memory_strength ADD COLUMN last_utility TEXT")
    with suppress(Exception):
        db.execute("ALTER TABLE memory_strength ADD COLUMN interference_count INTEGER DEFAULT 0")
    with suppress(Exception):
        db.execute("ALTER TABLE memory_strength ADD COLUMN link_count INTEGER DEFAULT 0")
    with suppress(Exception):
        db.execute("ALTER TABLE memory_strength ADD COLUMN emotion_peak REAL DEFAULT 0.0")
    with suppress(Exception):
        db.execute("ALTER TABLE memory_strength ADD COLUMN is_ltm INTEGER DEFAULT 0")

    db.commit()
