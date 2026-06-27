"""Migration 020: Add body_state and state_snapped_at columns to memories table.

These columns store a snapshot of the persona's emotional/physical state
at memory creation time, enabling "similar state" memory search.
"""

from __future__ import annotations


def upgrade(db) -> None:
    """Add body_state and state_snapped_at columns to memories."""
    existing = {r[1] for r in db.execute("PRAGMA table_info(memories)").fetchall()}
    if "body_state" not in existing:
        db.execute("ALTER TABLE memories ADD COLUMN body_state TEXT")
    if "state_snapped_at" not in existing:
        db.execute("ALTER TABLE memories ADD COLUMN state_snapped_at TEXT")
    db.commit()
