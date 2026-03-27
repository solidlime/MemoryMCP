from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from memory_mcp.domain.persona.entities import (
    ContextEntry,
    EmotionRecord,
    PersonaState,
)
from memory_mcp.domain.shared.errors import RepositoryError
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.domain.shared.time_utils import format_iso, get_now, parse_iso
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection

logger = get_logger(__name__)


class SQLitePersonaRepository:
    """SQLite-backed implementation of the PersonaRepository protocol."""

    def __init__(self, connection: SQLiteConnection) -> None:
        self._conn = connection

    @property
    def _db(self):
        return self._conn.get_memory_db()

    # ------------------------------------------------------------------
    # Persona state (bi-temporal)
    # ------------------------------------------------------------------

    def get_current_state(self, persona: str) -> Result[PersonaState, RepositoryError]:
        """Build the current persona state from context_state, user_info, persona_info."""
        try:
            # Get current context values (valid_until IS NULL means "current")
            rows = self._db.execute(
                """
                SELECT key, value FROM context_state
                WHERE persona = ? AND valid_until IS NULL
                """,
                (persona,),
            ).fetchall()
            state_map: dict[str, str] = {row["key"]: row["value"] for row in rows}

            # Get user_info
            user_rows = self._db.execute(
                "SELECT key, value FROM user_info WHERE persona = ?",
                (persona,),
            ).fetchall()
            user_info = {row["key"]: row["value"] for row in user_rows}

            # Get persona_info
            persona_rows = self._db.execute(
                "SELECT key, value FROM persona_info WHERE persona = ?",
                (persona,),
            ).fetchall()
            persona_info = {}
            for row in persona_rows:
                try:
                    persona_info[row["key"]] = json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    persona_info[row["key"]] = row["value"]

            return Success(
                PersonaState(
                    persona=persona,
                    emotion=state_map.get("emotion", "neutral"),
                    emotion_intensity=float(state_map.get("emotion_intensity", "0.0")),
                    physical_state=state_map.get("physical_state"),
                    mental_state=state_map.get("mental_state"),
                    environment=state_map.get("environment"),
                    relationship_status=state_map.get("relationship_status"),
                    fatigue=_safe_float(state_map.get("fatigue")),
                    warmth=_safe_float(state_map.get("warmth")),
                    arousal=_safe_float(state_map.get("arousal")),
                    heart_rate=state_map.get("heart_rate"),
                    touch_response=state_map.get("touch_response"),
                    action_tag=state_map.get("action_tag"),
                    speech_style=state_map.get("speech_style"),
                    user_info=user_info,
                    persona_info=persona_info,
                    last_conversation_time=_resolve_last_conversation_time(self._db, state_map),
                )
            )
        except Exception as e:
            logger.error("Failed to get persona state for '%s': %s", persona, e)
            return Failure(RepositoryError(str(e)))

    def update_state(
        self,
        persona: str,
        key: str,
        value: str,
        source: str | None = None,
    ) -> Result[None, RepositoryError]:
        """Update a single state key using bi-temporal pattern.

        1. Close the current record (set valid_until = now)
        2. Insert a new record with valid_from = now
        """
        try:
            now = format_iso(get_now())
            # Close current record
            self._db.execute(
                """
                UPDATE context_state
                SET valid_until = ?
                WHERE persona = ? AND key = ? AND valid_until IS NULL
                """,
                (now, persona, key),
            )
            # Insert new record
            self._db.execute(
                """
                INSERT INTO context_state (persona, key, value, valid_from, change_source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (persona, key, value, now, source),
            )
            self._db.commit()
            logger.info("State updated: persona=%s key=%s", persona, key)
            return Success(None)
        except Exception as e:
            logger.error("Failed to update state %s/%s: %s", persona, key, e)
            return Failure(RepositoryError(str(e)))

    def get_state_history(self, persona: str, key: str, limit: int = 20) -> Result[list[ContextEntry], RepositoryError]:
        """Get the change history for a specific state key."""
        try:
            rows = self._db.execute(
                """
                SELECT * FROM context_state
                WHERE persona = ? AND key = ?
                ORDER BY valid_from DESC
                LIMIT ?
                """,
                (persona, key, limit),
            ).fetchall()
            return Success([self._row_to_context_entry(r) for r in rows])
        except Exception as e:
            logger.error("Failed to get state history %s/%s: %s", persona, key, e)
            return Failure(RepositoryError(str(e)))

    # ------------------------------------------------------------------
    # Emotion history
    # ------------------------------------------------------------------

    def add_emotion_record(self, persona: str, record: EmotionRecord) -> Result[None, RepositoryError]:
        """Add an emotion record to history."""
        try:
            now = format_iso(get_now())
            self._db.execute(
                """
                INSERT INTO emotion_history
                    (emotion_type, intensity, timestamp, trigger_memory_key, context)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.emotion_type,
                    record.intensity,
                    format_iso(record.timestamp) if record.timestamp else now,
                    record.trigger_memory_key,
                    record.context,
                ),
            )
            self._db.commit()
            logger.info("Emotion record added: %s (%.1f)", record.emotion_type, record.intensity)
            return Success(None)
        except Exception as e:
            logger.error("Failed to add emotion record: %s", e)
            return Failure(RepositoryError(str(e)))

    def get_emotion_history(self, persona: str, limit: int = 20) -> Result[list[EmotionRecord], RepositoryError]:
        """Get recent emotion history."""
        try:
            rows = self._db.execute(
                """
                SELECT * FROM emotion_history
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return Success([self._row_to_emotion_record(r) for r in rows])
        except Exception as e:
            logger.error("Failed to get emotion history: %s", e)
            return Failure(RepositoryError(str(e)))

    def get_emotion_history_by_days(self, persona: str, days: int = 7) -> Result[list[EmotionRecord], RepositoryError]:
        """Get emotion history for the last N days, ordered by timestamp ascending."""
        try:
            from datetime import timedelta

            cutoff = get_now() - timedelta(days=days)
            rows = self._db.execute(
                """
                SELECT * FROM emotion_history
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (cutoff.isoformat(),),
            ).fetchall()
            return Success([self._row_to_emotion_record(r) for r in rows])
        except Exception as e:
            logger.error("Failed to get emotion history by days: %s", e)
            return Failure(RepositoryError(str(e)))

    # ------------------------------------------------------------------
    # User / Persona info (key-value store)
    # ------------------------------------------------------------------

    def set_user_info(self, persona: str, key: str, value: str) -> Result[None, RepositoryError]:
        """Set a user info key-value pair (upsert)."""
        try:
            now = format_iso(get_now())
            self._db.execute(
                """
                INSERT OR REPLACE INTO user_info (persona, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (persona, key, value, now),
            )
            self._db.commit()
            return Success(None)
        except Exception as e:
            logger.error("Failed to set user_info %s/%s: %s", persona, key, e)
            return Failure(RepositoryError(str(e)))

    def set_persona_info(self, persona: str, key: str, value: str) -> Result[None, RepositoryError]:
        """Set a persona info key-value pair (upsert)."""
        try:
            now = format_iso(get_now())
            self._db.execute(
                """
                INSERT OR REPLACE INTO persona_info (persona, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (persona, key, value, now),
            )
            self._db.commit()
            return Success(None)
        except Exception as e:
            logger.error("Failed to set persona_info %s/%s: %s", persona, key, e)
            return Failure(RepositoryError(str(e)))

    def get_user_info(self, persona: str) -> Result[dict, RepositoryError]:
        """Get all user_info for a persona."""
        try:
            rows = self._db.execute(
                "SELECT key, value FROM user_info WHERE persona = ?",
                (persona,),
            ).fetchall()
            return Success({row["key"]: row["value"] for row in rows})
        except Exception as e:
            logger.error("Failed to get user_info for '%s': %s", persona, e)
            return Failure(RepositoryError(str(e)))

    def get_persona_info(self, persona: str) -> Result[dict, RepositoryError]:
        """Get all persona_info for a persona."""
        try:
            rows = self._db.execute(
                "SELECT key, value FROM persona_info WHERE persona = ?",
                (persona,),
            ).fetchall()
            return Success({row["key"]: row["value"] for row in rows})
        except Exception as e:
            logger.error("Failed to get persona_info for '%s': %s", persona, e)
            return Failure(RepositoryError(str(e)))

    def sync_goals(self, persona: str, goals: list | str) -> Result[None, RepositoryError]:
        """persona_info の goals リストを goals テーブルに同期（全件置換）。"""
        try:
            if isinstance(goals, str):
                try:
                    goals = json.loads(goals)
                except Exception:
                    goals = [goals] if goals else []
            if not isinstance(goals, list):
                goals = []

            now = format_iso(get_now())
            db = self._db

            # 既存の active な goals を全件 inactive に
            db.execute("UPDATE goals SET status='inactive', updated_at=?", (now,))

            # 新しい goals を INSERT OR REPLACE
            for text in goals:
                if not text:
                    continue
                gid = hashlib.md5(f"{persona}:{text}".encode()).hexdigest()[:12]
                db.execute(
                    """
                    INSERT OR REPLACE INTO goals (id, description, status, priority, created_at, updated_at)
                    VALUES (?, ?, 'active', 0, COALESCE((SELECT created_at FROM goals WHERE id=?), ?), ?)
                    """,
                    (gid, str(text), gid, now, now),
                )
            db.commit()
            logger.info("Goals synced for persona '%s': %d entries", persona, len(goals))
            return Success(None)
        except Exception as e:
            logger.error("Failed to sync goals for '%s': %s", persona, e)
            return Failure(RepositoryError(str(e)))

    def sync_promises(self, persona: str, promises: list | str) -> Result[None, RepositoryError]:
        """persona_info の promises リストを promises テーブルに同期（全件置換）。"""
        try:
            if isinstance(promises, str):
                try:
                    promises = json.loads(promises)
                except Exception:
                    promises = [promises] if promises else []
            if not isinstance(promises, list):
                promises = []

            now = format_iso(get_now())
            db = self._db

            # 既存の active な promises を全件 inactive に
            db.execute("UPDATE promises SET status='inactive', updated_at=?", (now,))

            # 新しい promises を INSERT OR REPLACE
            for text in promises:
                if not text:
                    continue
                pid = hashlib.md5(f"{persona}:{text}".encode()).hexdigest()[:12]
                db.execute(
                    """
                    INSERT OR REPLACE INTO promises (id, description, status, priority, created_at, updated_at)
                    VALUES (?, ?, 'active', 0, COALESCE((SELECT created_at FROM promises WHERE id=?), ?), ?)
                    """,
                    (pid, str(text), pid, now, now),
                )
            db.commit()
            logger.info("Promises synced for persona '%s': %d entries", persona, len(promises))
            return Success(None)
        except Exception as e:
            logger.error("Failed to sync promises for '%s': %s", persona, e)
            return Failure(RepositoryError(str(e)))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_context_entry(row) -> ContextEntry:
        return ContextEntry(
            persona=row["persona"],
            key=row["key"],
            value=row["value"],
            valid_from=parse_iso(row["valid_from"]),
            valid_until=_parse_or_none(row["valid_until"]),
            change_source=row["change_source"],
        )

    @staticmethod
    def _row_to_emotion_record(row) -> EmotionRecord:
        return EmotionRecord(
            id=row["id"],
            emotion_type=row["emotion_type"],
            intensity=row["intensity"] or 0.5,
            timestamp=parse_iso(row["timestamp"]),
            trigger_memory_key=row["trigger_memory_key"],
            context=row["context"],
        )


def _resolve_last_conversation_time(db, state_map: dict):
    """Derive last conversation time from the most recent memory operation.

    Falls back to the stored context_state value if no memories exist.
    """
    try:
        row = db.execute("SELECT MAX(COALESCE(updated_at, created_at)) AS last_activity FROM memories").fetchone()
        if row and row["last_activity"]:
            memory_time = parse_iso(row["last_activity"])
            stored_time = _parse_or_none(state_map.get("last_conversation_time"))
            candidates = [t for t in (memory_time, stored_time) if t is not None]
            return max(candidates) if candidates else None
    except Exception:
        pass
    return _parse_or_none(state_map.get("last_conversation_time"))


def _safe_float(value: str | None) -> float | None:
    """Safely convert a string to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_or_none(value: str | None):
    """Parse ISO datetime or return None."""
    if not value:
        return None
    try:
        return parse_iso(value)
    except Exception:
        return None
