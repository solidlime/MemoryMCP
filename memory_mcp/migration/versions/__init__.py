from __future__ import annotations

from memory_mcp.migration.versions.v001_initial import upgrade as v001_upgrade
from memory_mcp.migration.versions.v002_add_source_context import (
    upgrade as v002_upgrade,
)

ALL_MIGRATIONS: list[tuple[str, str, object]] = [
    ("001", "Initial schema", v001_upgrade),
    ("002", "Add source_context to memories", v002_upgrade),
]
