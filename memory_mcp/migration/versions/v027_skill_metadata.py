from __future__ import annotations

from contextlib import suppress


def upgrade(db) -> None:
    """Add license, compatibility, metadata columns to skills table."""
    for col in ("license", "compatibility", "metadata"):
        with suppress(Exception):
            db.execute(f"ALTER TABLE skills ADD COLUMN {col} TEXT")
    db.commit()
