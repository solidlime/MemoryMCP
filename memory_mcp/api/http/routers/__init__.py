from memory_mcp.api.http.routers.admin import register_admin_routes
from memory_mcp.api.http.routers.chat import register_chat_routes
from memory_mcp.api.http.routers.item import register_item_routes
from memory_mcp.api.http.routers.memory import register_memory_routes
from memory_mcp.api.http.routers.persona import register_persona_routes
from memory_mcp.api.http.routers.search import register_search_routes

__all__ = [
    "register_admin_routes",
    "register_chat_routes",
    "register_item_routes",
    "register_memory_routes",
    "register_persona_routes",
    "register_search_routes",
]
