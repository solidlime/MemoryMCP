"""Migration 018: Add multi-dimensional emotions support.

- Adds emotions TEXT column to memories table (JSON dict of 9 basic emotions)
- Adds emotions TEXT column to emotion_history table
- Backfills existing emotion data into multi-dimensional format
"""

from __future__ import annotations

import contextlib
import json

BASIC_EMOTIONS = [
    "joy",
    "sadness",
    "anger",
    "fear",
    "disgust",
    "surprise",
    "love",
    "trust",
    "anticipation",
]


def upgrade(db) -> None:
    """Add emotions columns and backfill existing data."""
    # 1. Add emotions column to memories
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE memories ADD COLUMN emotions TEXT")

    # 2. Add emotions column to emotion_history
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE emotion_history ADD COLUMN emotions TEXT")

    # 3. Backfill memories: convert emotion + emotion_intensity to emotions JSON
    rows = db.execute("SELECT key, emotion, emotion_intensity FROM memories WHERE emotions IS NULL").fetchall()

    for row in rows:
        emotion_name = (row["emotion"] or "neutral").strip().lower()
        intensity = float(row["emotion_intensity"] or 0.0)

        emotions = {e: 0.0 for e in BASIC_EMOTIONS}
        if emotion_name in emotions:
            emotions[emotion_name] = intensity

        db.execute(
            "UPDATE memories SET emotions = ? WHERE key = ?",
            (json.dumps(emotions), row["key"]),
        )

    # 4. Backfill emotion_history
    hist_rows = db.execute("SELECT id, emotion_type, intensity FROM emotion_history WHERE emotions IS NULL").fetchall()

    for row in hist_rows:
        emotion_name = (row["emotion_type"] or "neutral").strip().lower()
        intensity = float(row["intensity"] or 0.0)

        emotions = {e: 0.0 for e in BASIC_EMOTIONS}
        if emotion_name in emotions:
            emotions[emotion_name] = intensity

        db.execute(
            "UPDATE emotion_history SET emotions = ? WHERE id = ?",
            (json.dumps(emotions), row["id"]),
        )

    db.commit()
