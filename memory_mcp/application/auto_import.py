"""Auto-import service: scan import directory and process legacy .zip files."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.config.settings import Settings
from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection
from memory_mcp.migration.engine import MigrationEngine
from memory_mcp.migration.importers.legacy_importer import LegacyImporter

logger = get_logger(__name__)


def run_auto_import(
    settings: Settings,
    *,
    import_dir: str | None = None,
) -> dict[str, dict[str, int]]:
    """Scan import directory and import all .zip files found.

    Returns a dict mapping persona names to their import counts.
    """
    effective_import_dir = import_dir or settings.import_dir
    if not effective_import_dir:
        return {}

    import_path = Path(effective_import_dir)

    if not import_path.exists():
        import_path.mkdir(parents=True, exist_ok=True)
        return {}

    zip_files: list[Path] = list(import_path.glob("*.zip"))
    if not zip_files:
        return {}

    results: dict[str, dict[str, int]] = {}

    for zip_path in zip_files:
        persona: str = zip_path.stem
        logger.info("Auto-importing '%s' from %s", persona, zip_path)

        connection = SQLiteConnection(settings.data_dir, persona)
        try:
            connection.initialize_schema()
            MigrationEngine(connection).run_all()

            importer = LegacyImporter(connection, persona)
            result = importer.import_from_zip(str(zip_path))

            if not result.is_ok:
                logger.error(
                    "Import failed for '%s': %s",
                    persona,
                    result.error,
                )
                continue

            counts: dict[str, int] = result.value

            # ------ vector store sync (best-effort) ------
            try:
                from memory_mcp.application.use_cases import (
                    AppContextRegistry,
                )

                ctx = AppContextRegistry.get(persona)
                if ctx.vector_store is not None:
                    ctx.vector_store.rebuild_collection(persona)
                    rows = connection.get_memory_db().execute("SELECT key, content FROM memories").fetchall()
                    memories_for_vector: list[tuple[str, str]] = [(row["key"], row["content"]) for row in rows]
                    if memories_for_vector:
                        upsert_result = ctx.vector_store.upsert_batch(persona, memories_for_vector)
                        if upsert_result.is_ok:
                            logger.info(
                                "Vector store synced for '%s': %d points",
                                persona,
                                upsert_result.value,
                            )
                        else:
                            logger.warning(
                                "Vector upsert failed for '%s': %s",
                                persona,
                                upsert_result.error,
                            )
                else:
                    logger.info(
                        "Qdrant unavailable — skipping vector sync for '%s'",
                        persona,
                    )
            except Exception:
                logger.warning(
                    "Vector sync failed for '%s' (non-fatal)",
                    persona,
                    exc_info=True,
                )

            # ------ move processed zip to done/ ------
            done_dir: Path = import_path / "done"
            done_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(zip_path), str(done_dir / zip_path.name))
            logger.info("Moved %s to %s", zip_path.name, done_dir)

            results[persona] = counts
        except Exception:
            logger.error(
                "Unexpected error importing '%s'",
                persona,
                exc_info=True,
            )
            continue
        finally:
            connection.close()

    return results
