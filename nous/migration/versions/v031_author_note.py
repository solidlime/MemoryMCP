from __future__ import annotations

from contextlib import suppress


def upgrade(db) -> None:
    """Add author_note and author_note_frequency columns to context_state.

    context_state is a key-value table where persona state fields (emotion,
    physical_state, etc.) are stored as rows. author_note and
    author_note_frequency will be stored as key-value pairs via the same
    mechanism. The ALTER TABLE is a defensive safety net so the columns
    exist if any direct-COLUMN queries are used.
    """
    for col in ("author_note", "author_note_frequency"):
        with suppress(Exception):
            db.execute(f"ALTER TABLE context_state ADD COLUMN {col} TEXT")

    # Default frequency for existing rows that might get set
    db.execute(
        "UPDATE context_state SET author_note_frequency = 'always' "
        "WHERE key = 'author_note_frequency' AND author_note_frequency IS NULL"
    )

    db.commit()
