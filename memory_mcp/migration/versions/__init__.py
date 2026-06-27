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
from memory_mcp.migration.versions.v015_chat_display_housekeeping import upgrade as v015_upgrade
from memory_mcp.migration.versions.v016_chat_sandbox import upgrade as v016_upgrade
from memory_mcp.migration.versions.v017_chat_mental_model import upgrade as v017_upgrade
from memory_mcp.migration.versions.v018_multi_emotions import upgrade as v018_upgrade
from memory_mcp.migration.versions.v019_body_state_refine import upgrade as v019_upgrade
from memory_mcp.migration.versions.v020_memory_body_state import upgrade as v020_upgrade
from memory_mcp.migration.versions.v021_remove_multi_emotions import (
    upgrade as v021_upgrade,
)
from memory_mcp.migration.versions.v022_context_compression import (
    upgrade as v022_upgrade,
)
from memory_mcp.migration.versions.v024_session_events import upgrade as v024_upgrade
from memory_mcp.migration.versions.v025_searxng_url import upgrade as v025_upgrade
from memory_mcp.migration.versions.v026_image_gen import upgrade as v026_upgrade
from memory_mcp.migration.versions.v027_skill_metadata import (
    upgrade as v027_upgrade,
)
from memory_mcp.migration.versions.v028_lifecycle_status import (
    upgrade as v028_upgrade,
)

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
    ("015", "Add display_history_turns and housekeeping_threshold to chat_settings", v015_upgrade),
    ("016", "Add sandbox_enabled to chat_settings", v016_upgrade),
    ("017", "Add mental_model_enabled and mental_model_min_samples to chat_settings", v017_upgrade),
    ("018", "Add multi-dimensional emotions support", v018_upgrade),
    ("019", "Refine body_state: heart_rate numeric, pain added", v019_upgrade),
    ("020", "Add body_state and state_snapped_at to memories", v020_upgrade),
    ("021", "Remove multi-dimensional emotions support", v021_upgrade),
    ("022", "Add context compression and parallel tools columns", v022_upgrade),
    ("024", "Add session_events table for context-mode style recording", v024_upgrade),
    ("025", "Add searxng_url column to chat_settings", v025_upgrade),
    ("026", "Add image_gen columns to chat_settings", v026_upgrade),
    ("027", "Add license/compatibility/metadata to skills table", v027_upgrade),
    ("028", "Add lifecycle_status column to memories table", v028_upgrade),
]
