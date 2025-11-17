"""
MCP Tool Registration Module

Registers MCP tools and resources in a centralized location.
All tool functions are implemented in the tools/ package and registered here.

Architecture:
- Public API: 3 unified tools (memory, item, get_context)
- Internal: Individual tool implementations in tools/ subdirectory
- Admin tools: Available via admin_tools.py CLI or dashboard

Phase 35 (2025-11-16): Unified tool interface
- Consolidated 12 individual tools into 3 unified tools
- 75% reduction in tool count for better context efficiency
"""

from typing import Any


def register_tools(mcp: Any) -> None:
    """Register MCP tools.
    
    Public API (3 tools):
        - get_context: Current persona state, time, memory stats
        - memory: Unified memory operations (create, read, update, delete, search, stats)
        - item: Unified item operations (add, remove, equip, unequip, update, search, history, memories, stats)
    """
    from tools.unified_tools import memory, item
    from tools.context_tools import get_context
    
    # Context retrieval (call every response)
    mcp.tool()(get_context)
    
    # Unified memory interface
    mcp.tool()(memory)
    
    # Unified item interface
    mcp.tool()(item)


def register_resources(mcp: Any) -> None:
    """Register MCP resources.
    
    Resources:
        - memory://info: Memory system information
        - memory://metrics: Memory metrics and statistics
        - memory://stats: Detailed memory statistics
        - memory://cleanup: Cleanup suggestions
    """
    from src.resources import (
        get_memory_info,
        get_memory_metrics,
        get_memory_stats,
        get_cleanup_suggestions,
    )
    
    mcp.resource("memory://info")(get_memory_info)
    mcp.resource("memory://metrics")(get_memory_metrics)
    mcp.resource("memory://stats")(get_memory_stats)
    mcp.resource("memory://cleanup")(get_cleanup_suggestions)


