from __future__ import annotations

from memory_mcp.migration.versions.v001_initial import upgrade as v001_upgrade
from memory_mcp.migration.versions.v002_add_source_context import (
    upgrade as v002_upgrade,
)
from memory_mcp.migration.versions.v003_memory_versions import (
    upgrade as v003_upgrade,
)
from memory_mcp.migration.versions.v004_entity_graph import upgrade as v004_upgrade
from memory_mcp.migration.versions.v005_search_log import upgrade as v005_upgrade
from memory_mcp.migration.versions.v006_normalize_emotions import (
    upgrade as v006_upgrade,
)
from memory_mcp.migration.versions.v007_add_performance_indexes import (
    upgrade as v007_upgrade,
)
from memory_mcp.migration.versions.v008_add_persona_to_goals_promises import (
    upgrade as v008_upgrade,
)
from memory_mcp.migration.versions.v009_goals_promises_to_memories import (
    upgrade as v009_upgrade,
)
from memory_mcp.migration.versions.v010_chat_settings import upgrade as v010_upgrade
from memory_mcp.migration.versions.v011_chat_extract_settings import upgrade as v011_upgrade
from memory_mcp.migration.versions.v012_chat_mcp_servers import upgrade as v012_upgrade
from memory_mcp.migration.versions.v013_chat_skills import upgrade as v013_upgrade
from memory_mcp.migration.versions.v014_chat_reflection_retrieval import upgrade as v014_upgrade

ALL_MIGRATIONS: list[tuple[str, str, object]] = [
    ("001", "Initial schema", v001_upgrade),
    ("002", "Add source_context to memories", v002_upgrade),
    ("003", "Add memory_versions table", v003_upgrade),
    ("004", "Add entity graph tables", v004_upgrade),
    ("005", "Add search_log table", v005_upgrade),
    ("006", "Normalize emotion_type values in memories table", v006_upgrade),
    ("007", "Add performance indexes", v007_upgrade),
    ("008", "Add persona column to goals and promises tables", v008_upgrade),
    ("009", "Migrate goals/promises tables to memory tags", v009_upgrade),
    ("010", "Add chat_settings table", v010_upgrade),
    ("011", "Add auto extract settings to chat_settings", v011_upgrade),
    ("012", "Add MCP servers and tool_result_max_chars to chat_settings", v012_upgrade),
    ("013", "Add skills table and enabled_skills to chat_settings", v013_upgrade),
    ("014", "Add reflection and retrieval weight settings to chat_settings", v014_upgrade),
]
