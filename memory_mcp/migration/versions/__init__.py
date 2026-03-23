from __future__ import annotations

from memory_mcp.migration.versions.v001_initial import upgrade as v001_upgrade
from memory_mcp.migration.versions.v002_add_source_context import (
    upgrade as v002_upgrade,
)
from memory_mcp.migration.versions.v003_memory_versions import (
    upgrade as v003_upgrade,
)
from memory_mcp.migration.versions.v004_entity_graph import upgrade as v004_upgrade

ALL_MIGRATIONS: list[tuple[str, str, object]] = [
    ("001", "Initial schema", v001_upgrade),
    ("002", "Add source_context to memories", v002_upgrade),
    ("003", "Add memory_versions table", v003_upgrade),
    ("004", "Add entity graph tables", v004_upgrade),
]
