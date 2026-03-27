"""Migration v008: Add persona column to goals and promises tables."""

from __future__ import annotations

VERSION = "008"
DESCRIPTION = "Add persona column to goals and promises tables"


def upgrade(db) -> None:
    """Add persona column, backfill with 'default'."""
    goals_cols = [row[1] for row in db.execute("PRAGMA table_info(goals)").fetchall()]
    if "persona" not in goals_cols:
        db.execute("ALTER TABLE goals ADD COLUMN persona TEXT DEFAULT 'default'")
        db.execute("UPDATE goals SET persona = 'default' WHERE persona IS NULL")
        db.execute("CREATE INDEX IF NOT EXISTS idx_goals_persona ON goals(persona)")
    promises_cols = [row[1] for row in db.execute("PRAGMA table_info(promises)").fetchall()]
    if "persona" not in promises_cols:
        db.execute("ALTER TABLE promises ADD COLUMN persona TEXT DEFAULT 'default'")
        db.execute("UPDATE promises SET persona = 'default' WHERE persona IS NULL")
        db.execute("CREATE INDEX IF NOT EXISTS idx_promises_persona ON promises(persona)")
