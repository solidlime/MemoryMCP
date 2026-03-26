"""Dashboard section modules for the MemoryMCP WebUI."""

from .admin import render_admin_js, render_admin_tab
from .analytics import render_analytics_js, render_analytics_tab
from .base import render_head, render_layout_shell, render_nav, render_utilities_js
from .import_export import render_import_export_js, render_import_export_tab
from .knowledge_graph import render_graph_js, render_graph_tab
from .memories import render_memories_js, render_memories_tab
from .overview import render_overview_js, render_overview_tab
from .persona import render_persona_js, render_persona_tab
from .settings import render_settings_js, render_settings_tab

__all__ = [
    "render_head",
    "render_nav",
    "render_utilities_js",
    "render_layout_shell",
    "render_overview_tab",
    "render_overview_js",
    "render_analytics_tab",
    "render_analytics_js",
    "render_memories_tab",
    "render_memories_js",
    "render_graph_tab",
    "render_graph_js",
    "render_import_export_tab",
    "render_import_export_js",
    "render_persona_tab",
    "render_persona_js",
    "render_settings_tab",
    "render_settings_js",
    "render_admin_tab",
    "render_admin_js",
]
