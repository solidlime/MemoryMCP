from __future__ import annotations

from contextlib import suppress


def upgrade(db) -> None:
    """Add lifecycle_status column to memories table with data migration.

    Existing data migration:
    - New memories default to lifecycle_status = 'active'
    - "active" tag is NOT removed from tags (goal/promise status uses tags independently)
    """
    # Add column using IF NOT EXISTS pattern (safe for re-runs)
    with suppress(Exception):
        db.execute("ALTER TABLE memories ADD COLUMN lifecycle_status TEXT DEFAULT 'active'")

    # Set lifecycle_status for any rows where it's NULL (defensive)
    db.execute("UPDATE memories SET lifecycle_status = 'active' WHERE lifecycle_status IS NULL")

    db.commit()
