"""Migration 019: Refine body_state — heart_rate numeric, remove touch_response, add pain.

- Resets heart_rate context_state values to "0.5" (old Japanese text → numeric default)
- Adds pain float field support
"""

from __future__ import annotations


def upgrade(db) -> None:
    """Reset heart_rate to numeric default, no schema changes needed."""
    # Reset heart_rate to numeric default (old values were free-text Japanese)
    db.execute("UPDATE context_state SET value = '0.5' WHERE key = 'heart_rate' AND valid_until IS NULL")
    # Pain is new — no existing data to migrate
    db.commit()
