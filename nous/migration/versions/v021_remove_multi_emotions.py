"""Migration 021: Remove multi-dimensional emotions support.

Reverts the multi-dimensional emotions system (v018) back to single
emotion tag + intensity. Drops the `emotions TEXT` columns from both
`memories` and `emotion_history` tables.
"""

from __future__ import annotations

import contextlib


def upgrade(db) -> None:
    """Drop emotions TEXT columns."""
    # SQLite doesn't support DROP COLUMN in older versions,
    # but the columns can be left as dead columns.
    # We use ALTER TABLE DROP COLUMN (supported since SQLite 3.35.0).
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE memories DROP COLUMN emotions")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE emotion_history DROP COLUMN emotions")
    db.commit()
