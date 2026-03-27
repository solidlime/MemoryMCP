from __future__ import annotations

from memory_mcp.api.http.routers import (
    register_admin_routes,
    register_item_routes,
    register_memory_routes,
    register_persona_routes,
    register_search_routes,
)


def register_http_routes(mcp) -> None:
    """Register HTTP routes on the FastMCP server."""
    register_persona_routes(mcp)
    register_memory_routes(mcp)
    register_search_routes(mcp)
    register_item_routes(mcp)
    register_admin_routes(mcp)
