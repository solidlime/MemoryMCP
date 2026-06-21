from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP  # noqa: TC002

from memory_mcp.api.mcp.middleware import get_current_persona
from memory_mcp.application.use_cases import AppContextRegistry

logger = logging.getLogger(__name__)




# =============================================================================
# Core tool implementations — shared between MCP and builtin
# =============================================================================


# ── Re-export core implementations from sub-modules ──
from memory_mcp.api.mcp._tools_goal import _tool_goal_manage, _tool_promise_manage  # noqa: E402, F401
from memory_mcp.api.mcp._tools_helpers import (  # noqa: E402, F401
    _build_time_comment,
    _format_lightweight_response,
    _format_state_block,
    _format_state_diff,
    _parse_days_from_relative,
)
from memory_mcp.api.mcp._tools_item import (  # noqa: E402, F401
    _tool_item_add,
    _tool_item_equip,
    _tool_item_history,
    _tool_item_remove,
    _tool_item_search,
    _tool_item_unequip,
    _tool_item_update,
)
from memory_mcp.api.mcp._tools_memory import (  # noqa: E402, F401
    _tool_memory_create,
    _tool_memory_delete,
    _tool_memory_read,
    _tool_memory_search,
    _tool_memory_stats,
    _tool_memory_update,
)
from memory_mcp.api.mcp._tools_persona import _tool_get_context, _tool_update_context  # noqa: E402, F401
from memory_mcp.api.mcp._tools_sandbox import _tool_sandbox, _tool_sandbox_files  # noqa: E402, F401
from memory_mcp.api.mcp._tools_skill import _tool_invoke_skill  # noqa: E402, F401

# =============================================================================
# Dispatch table — maps tool name → (core_function, docstring)
# =============================================================================

TOOL_DISPATCH: dict[str, Any] = {
    "get_context": _tool_get_context,
    "memory_create": _tool_memory_create,
    "memory_read": _tool_memory_read,
    "memory_update": _tool_memory_update,
    "memory_delete": _tool_memory_delete,
    "memory_search": _tool_memory_search,
    "memory_stats": _tool_memory_stats,
    "update_context": _tool_update_context,
    "item_add": _tool_item_add,
    "item_remove": _tool_item_remove,
    "item_equip": _tool_item_equip,
    "item_unequip": _tool_item_unequip,
    "item_update": _tool_item_update,
    "item_search": _tool_item_search,
    "item_history": _tool_item_history,
    "sandbox": _tool_sandbox,
    "sandbox_files": _tool_sandbox_files,
    "goal_manage": _tool_goal_manage,
    "promise_manage": _tool_promise_manage,
    "invoke_skill": _tool_invoke_skill,
}


# MCP registration — thin wrappers around core implementations
# =============================================================================


def register_tools(mcp: FastMCP) -> None:
    """Register flat-named MCP tools (20 tools)."""

    # get_context
    @mcp.tool()
    async def get_context() -> str:
        """Get persona state and memory overview. Call FIRST at session start.
        Lightweight: active commitments + essential story + body/emotion state (~500-800 tokens)."""
        p = _resolve_persona()
        return await _tool_get_context(AppContextRegistry.get(p), p)

    # memory_create
    @mcp.tool()
    async def memory_create(
        content: str = "",
        importance: float | None = None,
        tags: list[str] | None = None,
        privacy_level: str = "internal",
        source_context: str | None = None,
        defer_vector: bool = False,
    ) -> str:
        """Create a memory. Use to record important user facts, preferences, events.
        importance auto-evaluated via LLM when None and enrichment enabled.
        tags: categorization tags. defer_vector: skip immediate vector indexing.

        **Important**: Call context_update/update_context *before* memory_create
        if your emotional or physical state has changed. The system automatically
        snapshots your current persona state (emotions + body_state) at memory creation time —
        this enables searching memories by the emotional/physical context in which they were created."""
        p = _resolve_persona()
        return await _tool_memory_create(
            AppContextRegistry.get(p),
            p,
            content=content,
            importance=importance,
            tags=tags,
            privacy_level=privacy_level,
            source_context=source_context,
            defer_vector=defer_vector,
        )

    # memory_read
    @mcp.tool()
    async def memory_read(memory_key: str | None = None, limit: int = 10, offset: int = 0) -> str:
        """Read a memory by key, or list most recent if key omitted. Use limit/offset for pagination."""
        p = _resolve_persona()
        return await _tool_memory_read(AppContextRegistry.get(p), p, memory_key=memory_key, limit=limit, offset=offset)

    # memory_update
    @mcp.tool()
    async def memory_update(
        memory_key: str = "",
        content: str | None = None,
        importance: float | None = None,
        emotion: str | None = None,
        emotion_intensity: float | None = None,
        tags: list[str] | None = None,
        privacy_level: str | None = None,
    ) -> str:
        """Update a memory. Only provided fields are changed.
        importance must be 0.0-1.0. Invalid emotion silently falls back to neutral."""
        p = _resolve_persona()
        return await _tool_memory_update(
            AppContextRegistry.get(p),
            p,
            memory_key=memory_key,
            content=content,
            importance=importance,
            emotion=emotion,
            emotion_intensity=emotion_intensity,
            tags=tags,
            privacy_level=privacy_level,
        )

    # memory_delete
    @mcp.tool()
    async def memory_delete(memory_key: str | None = None, query: str | None = None) -> str:
        """Delete a memory by key or search query. Shows deleted content snippet for confirmation."""
        p = _resolve_persona()
        return await _tool_memory_delete(AppContextRegistry.get(p), p, memory_key=memory_key, query=query)

    # memory_search
    @mcp.tool()
    async def memory_search(
        query: str,
        top_k: int = 5,
        tags: list[str] | None = None,
        date_range: str | None = None,
        min_importance: float | None = None,
        emotion: str | None = None,
        importance_weight: float = 0.0,
        recency_weight: float = 0.0,
    ) -> str:
        """Search memories with hybrid retrieval. Use when conversation references past events
        or you need context about the user. date_range: "7d","30d","昨日".
        importance_weight/recency_weight: RRF scoring boosts (0.0-1.0)."""
        p = _resolve_persona()
        return await _tool_memory_search(
            AppContextRegistry.get(p),
            p,
            query=query,
            top_k=top_k,
            tags=tags,
            date_range=date_range,
            min_importance=min_importance,
            emotion=emotion,
            importance_weight=importance_weight,
            recency_weight=recency_weight,
        )

    # memory_stats
    @mcp.tool()
    async def memory_stats(top_n: int = 20) -> str:
        """Get memory statistics: total count, tag/emotion distributions (top_n entries each)."""
        p = _resolve_persona()
        return await _tool_memory_stats(AppContextRegistry.get(p), p, top_n=top_n)

    # update_context
    @mcp.tool()
    async def update_context(
        emotion: str | None = None,
        emotion_intensity: float | None = None,
        physical_state: str | None = None,
        mental_state: str | None = None,
        environment: str | None = None,
        relationship_status: str | None = None,
        body_state: dict | None = None,
        speech_style: str | None = None,
        context_note: str | None = None,
        user_info: dict | None = None,
        persona_info: dict | None = None,
        nickname: str | None = None,
        relationship_type: str | None = None,
    ) -> str:
        """Update persona state. context_note: short note on current activity (session continuity).
        body_state: {fatigue, warmth, arousal, heart_rate, pain (0.0-1.0)}.
        user_info: {name, nickname, preferred_address}. persona_info: {nickname, ...}."""
        p = _resolve_persona()
        return await _tool_update_context(
            AppContextRegistry.get(p),
            p,
            emotion=emotion,
            emotion_intensity=emotion_intensity,
            physical_state=physical_state,
            mental_state=mental_state,
            environment=environment,
            relationship_status=relationship_status,
            body_state=body_state,
            speech_style=speech_style,
            context_note=context_note,
            user_info=user_info,
            persona_info=persona_info,
            nickname=nickname,
            relationship_type=relationship_type,
        )

    # item_add
    @mcp.tool()
    async def item_add(
        item_name: str = "",
        category: str | None = None,
        description: str | None = None,
        quantity: int = 1,
        tags: list[str] | None = None,
    ) -> str:
        """Add item to inventory. State changes (wet, dirty) should use item_update on existing items."""
        p = _resolve_persona()
        return await _tool_item_add(
            AppContextRegistry.get(p),
            p,
            item_name=item_name,
            category=category,
            description=description,
            quantity=quantity,
            tags=tags,
        )

    # item_remove
    @mcp.tool()
    async def item_remove(item_name: str = "") -> str:
        """Remove item from inventory by name."""
        p = _resolve_persona()
        return await _tool_item_remove(AppContextRegistry.get(p), p, item_name=item_name)

    # item_equip
    @mcp.tool()
    async def item_equip(equipment: dict | None = None, auto_add: bool = True) -> str:
        """Equip items to slots. equipment={"top":"白いドレス"}. Slots: top,bottom,shoes,outer,accessories,head."""
        p = _resolve_persona()
        return await _tool_item_equip(AppContextRegistry.get(p), p, equipment=equipment, auto_add=auto_add)

    # item_unequip
    @mcp.tool()
    async def item_unequip(slots: list[str] | str | None = None) -> str:
        """Unequip items from slots. slots: "top" or ["top","head"]."""
        p = _resolve_persona()
        return await _tool_item_unequip(AppContextRegistry.get(p), p, slots=slots)

    # item_update
    @mcp.tool()
    async def item_update(
        item_name: str = "",
        category: str | None = None,
        description: str | None = None,
        quantity: int = 1,
        tags: list[str] | None = None,
    ) -> str:
        """Update item properties. Only provided fields change. Use for state changes not new items."""
        p = _resolve_persona()
        return await _tool_item_update(
            AppContextRegistry.get(p),
            p,
            item_name=item_name,
            category=category,
            description=description,
            quantity=quantity,
            tags=tags,
        )

    # item_search
    @mcp.tool()
    async def item_search(query: str | None = None, category: str | None = None) -> str:
        """Search inventory by name query or category."""
        p = _resolve_persona()
        return await _tool_item_search(AppContextRegistry.get(p), p, query=query, category=category)

    # item_history
    @mcp.tool()
    async def item_history(days: int = 7) -> str:
        """Get equipment change history for the last N days."""
        p = _resolve_persona()
        return await _tool_item_history(AppContextRegistry.get(p), p, days=days)

    # sandbox
    @mcp.tool()
    async def sandbox(code: str, language: str = "python") -> str:
        """Execute code in Docker sandbox. State persists per session.
        language: "python" or "bash". Returns stdout, stderr, exit_code, artifacts (base64 images)."""
        p = _resolve_persona()
        return await _tool_sandbox(AppContextRegistry.get(p), p, code=code, language=language)

    # sandbox_files
    @mcp.tool()
    async def sandbox_files(operation: str, path: str = "/sandbox", content: str | None = None) -> str:
        """Sandbox file operations under /sandbox. operation: list/read/write/delete.
        read auto-detects images (PNG/JPEG/GIF/WebP) returning base64 with PIL resize support."""
        p = _resolve_persona()
        r = await _tool_sandbox_files(AppContextRegistry.get(p), p, operation=operation, path=path, content=content)
        return json.dumps(r, ensure_ascii=False)

    # goal_manage
    @mcp.tool()
    async def goal_manage(
        operation: str, content: str = "", importance: float = 0.75, memory_key: str | None = None
    ) -> str:
        """Manage goals. operation: create (new goal), achieve (mark done), cancel (abandon).
        Goals stored as memories with tags=["goal","active/achieved/cancelled"].
        For achieve/cancel, use memory_key to specify the goal directly (content can be empty)."""
        p = _resolve_persona()
        r = await _tool_goal_manage(
            AppContextRegistry.get(p),
            p,
            operation=operation,
            content=content,
            importance=importance,
            memory_key=memory_key,
        )
        if r.get("ok"):
            if "key" in r:
                return f"Goal created: {r['key']}"
            if "status" in r:
                return f"Goal {r['status']}: {r['content']}"
            return "Goal done"
        return f"Error: {r.get('error', 'unknown')}"

    # promise_manage
    @mcp.tool()
    async def promise_manage(
        operation: str, content: str = "", importance: float = 0.8, memory_key: str | None = None
    ) -> str:
        """Manage promises. operation: create (new promise), fulfill (mark done), cancel (abandon).
        Promises stored as memories with tags=["promise","active/fulfilled/cancelled"].
        For fulfill/cancel, use memory_key to specify the promise directly (content can be empty)."""
        p = _resolve_persona()
        r = await _tool_promise_manage(
            AppContextRegistry.get(p),
            p,
            operation=operation,
            content=content,
            importance=importance,
            memory_key=memory_key,
        )
        if r.get("ok"):
            if "key" in r:
                return f"Promise created: {r['key']}"
            if "status" in r:
                return f"Promise {r['status']}: {r['content']}"
            return "Promise done"
        return f"Error: {r.get('error', 'unknown')}"

    # invoke_skill
    @mcp.tool()
    async def invoke_skill(name: str, task: str) -> str:
        """Execute a skill in isolated LLM context. Loads skill from store,
        runs with chat config provider/model. Returns skill output text."""
        p = _resolve_persona()
        r = await _tool_invoke_skill(AppContextRegistry.get(p), p, name=name, task=task)
        if r.get("ok"):
            return r.get("result", "(no response)")
        return f"Error: {r.get('error', 'unknown')}"



def _resolve_persona() -> str:
    return get_current_persona()

