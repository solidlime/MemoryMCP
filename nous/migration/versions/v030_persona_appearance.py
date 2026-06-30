from __future__ import annotations

from contextlib import suppress


def upgrade(db) -> None:
    """Add visual_desc column to items table.

    Changes:
    - items: add visual_desc TEXT for item visual description
    """
    with suppress(Exception):
        db.execute("ALTER TABLE items ADD COLUMN visual_desc TEXT")

    db.commit()
