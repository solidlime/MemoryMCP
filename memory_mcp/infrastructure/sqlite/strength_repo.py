from __future__ import annotations

from memory_mcp.domain.memory.entities import MemoryStrength
from memory_mcp.domain.shared.errors import RepositoryError
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.domain.shared.time_utils import format_iso
from memory_mcp.infrastructure.logging.structured import get_logger

logger = get_logger(__name__)


class SQLiteStrengthMixin:
    """Mixin providing memory strength operations for SQLiteMemoryRepository."""

    def get_strength(self, key: str) -> Result[MemoryStrength | None, RepositoryError]:
        """Get the strength record for a memory."""
        try:
            row = self._db.execute("SELECT * FROM memory_strength WHERE memory_key = ?", (key,)).fetchone()
            if row is None:
                return Success(None)
            return Success(self._row_to_strength(row))
        except Exception as e:
            logger.error("Failed to get strength for %s: %s", key, e)
            return Failure(RepositoryError(str(e)))

    def save_strength(self, strength: MemoryStrength) -> Result[None, RepositoryError]:
        """Save or update a memory strength record."""
        try:
            self._db.execute(
                """
                INSERT OR REPLACE INTO memory_strength
                    (memory_key, strength, stability, last_decay, recall_count, last_recall)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    strength.memory_key,
                    strength.strength,
                    strength.stability,
                    format_iso(strength.last_decay) if strength.last_decay else None,
                    strength.recall_count,
                    format_iso(strength.last_recall) if strength.last_recall else None,
                ),
            )
            self._db.commit()
            return Success(None)
        except Exception as e:
            self._db.rollback()
            logger.error("Failed to save strength for %s: %s", strength.memory_key, e)
            return Failure(RepositoryError(str(e)))

    def get_all_strengths(self) -> Result[list[MemoryStrength], RepositoryError]:
        """Get all memory strength records."""
        try:
            rows = self._db.execute("SELECT * FROM memory_strength").fetchall()
            return Success([self._row_to_strength(r) for r in rows])
        except Exception as e:
            logger.error("Failed to get all strengths: %s", e)
            return Failure(RepositoryError(str(e)))

    def _row_to_strength(self, row) -> MemoryStrength:
        """Convert a database row to a MemoryStrength entity."""
        return MemoryStrength(
            memory_key=row["memory_key"],
            strength=row["strength"] or 1.0,
            stability=row["stability"] or 1.0,
            last_decay=self._parse_iso_or_none(row["last_decay"]),
            recall_count=row["recall_count"] or 0,
            last_recall=self._parse_iso_or_none(row["last_recall"]),
        )
