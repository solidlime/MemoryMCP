"""Migration v006: Normalize emotion_type values in memories table."""

from __future__ import annotations

import logging

from memory_mcp.domain.value_objects import normalize_emotion

VERSION = "006"
DESCRIPTION = "Normalize emotion_type values in memories table"

logger = logging.getLogger(__name__)


def upgrade(db) -> None:
    """Normalize all emotion_type values in memories table.

    Fetches all non-NULL emotion_type values, applies normalize_emotion(),
    and updates only rows where the value changed.
    """
    rows = db.execute("SELECT memory_key, emotion_type FROM memories WHERE emotion_type IS NOT NULL").fetchall()

    updated = 0
    for memory_key, emotion_type in rows:
        normalized = normalize_emotion(emotion_type)
        if normalized != emotion_type:
            db.execute(
                "UPDATE memories SET emotion_type = ? WHERE memory_key = ?",
                (normalized, memory_key),
            )
            updated += 1

    if updated > 0:
        logger.info("v006: normalized %d emotion_type value(s)", updated)
    else:
        logger.debug("v006: no emotion_type values needed normalization")


def downgrade(db) -> None:
    """Downgrade is a no-op: original values cannot be recovered."""
    logger.debug("v006: downgrade is a no-op (original emotion values not recoverable)")
