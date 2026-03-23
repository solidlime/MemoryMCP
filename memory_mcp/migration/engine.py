from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.domain.shared.errors import MigrationError
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.domain.shared.time_utils import format_iso, get_now

if TYPE_CHECKING:
    from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection


class MigrationEngine:
    """Lightweight migration engine for schema versioning."""

    def __init__(self, connection: SQLiteConnection) -> None:
        self.conn = connection
        self._ensure_migration_table()

    def _ensure_migration_table(self) -> None:
        db = self.conn.get_memory_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                version TEXT PRIMARY KEY,
                description TEXT,
                applied_at TEXT NOT NULL
            )
            """
        )
        db.commit()

    def get_current_version(self) -> str | None:
        db = self.conn.get_memory_db()
        row = db.execute(
            "SELECT version FROM _migrations ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def get_applied_versions(self) -> list[str]:
        db = self.conn.get_memory_db()
        rows = db.execute(
            "SELECT version FROM _migrations ORDER BY version"
        ).fetchall()
        return [r[0] for r in rows]

    def apply(self, version: str, description: str, upgrade_fn) -> Result:
        """Apply a single migration."""
        if version in self.get_applied_versions():
            return Success(None)

        db = self.conn.get_memory_db()
        try:
            upgrade_fn(db)
            db.execute(
                "INSERT INTO _migrations (version, description, applied_at) VALUES (?, ?, ?)",
                (version, description, format_iso(get_now())),
            )
            db.commit()
            return Success(None)
        except Exception as e:
            db.rollback()
            return Failure(MigrationError(f"Migration {version} failed: {e}"))

    def run_all(self) -> Result[list[str], MigrationError]:
        """Run all pending migrations in order."""
        from memory_mcp.migration.versions import ALL_MIGRATIONS

        applied: list[str] = []
        for version, description, upgrade_fn in ALL_MIGRATIONS:
            result = self.apply(version, description, upgrade_fn)
            if not result.is_ok:
                return Failure(result.error)
            applied.append(version)
        return Success(applied)
