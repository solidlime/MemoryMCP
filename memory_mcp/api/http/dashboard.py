"""MemoryMCP v2 Dashboard - Single Page Application.

A modular glassmorphism dashboard for managing persona memories,
analytics, settings, and administration. Each tab is defined in
its own module under ``sections/``.
"""

from .sections.admin import render_admin_js, render_admin_tab
from .sections.analytics import render_analytics_js, render_analytics_tab
from .sections.base import render_layout_shell, render_nav
from .sections.import_export import render_import_export_js, render_import_export_tab
from .sections.knowledge_graph import render_graph_js, render_graph_tab
from .sections.memories import render_memories_js, render_memories_tab
from .sections.overview import render_overview_js, render_overview_tab
from .sections.persona import render_persona_js, render_persona_tab
from .sections.settings import render_settings_js, render_settings_tab


def render_dashboard(persona: str | None = None) -> str:
    """Return the complete HTML string for the SPA dashboard."""
    tabs = [
        {"id": "overview", "icon": "📊", "label": "Overview"},
        {"id": "analytics", "icon": "📈", "label": "Analytics"},
        {"id": "memories", "icon": "🧠", "label": "Memories"},
        {"id": "graph", "icon": "🕸️", "label": "Graph"},
        {"id": "import-export", "icon": "📦", "label": "Import/Export"},
        {"id": "personas", "icon": "👤", "label": "Personas"},
        {"id": "settings", "icon": "⚙️", "label": "Settings"},
        {"id": "admin", "icon": "🔧", "label": "Admin"},
    ]

    nav_html = render_nav(tabs)

    tab_contents = "\n".join(
        [
            render_overview_tab(),
            render_analytics_tab(),
            render_memories_tab(),
            render_graph_tab(),
            render_import_export_tab(),
            render_persona_tab(),
            render_settings_tab(),
            render_admin_tab(),
        ]
    )

    tab_js = "\n".join(
        filter(
            None,
            [
                render_overview_js(),
                render_analytics_js(),
                render_memories_js(),
                render_graph_js(),
                render_import_export_js(),
                render_persona_js(),
                render_settings_js(),
                render_admin_js(),
            ],
        )
    )

    return render_layout_shell(nav_html, tab_contents, tab_js, initial_persona=persona)
