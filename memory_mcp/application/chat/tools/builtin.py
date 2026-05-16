"""Built-in tool executor and skill invocation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from memory_mcp.api.mcp.tools import TOOL_DISPATCH, _VALID_EMOTIONS
from memory_mcp.application.chat.tools.definitions import _MEMORY_MCP_TOOL_NAMES
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.infrastructure.llm.base import ToolDefinition
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)


def filter_extra_tools(extra_tools: list[ToolDefinition]) -> list[ToolDefinition]:
    """MCP extra ツールから memory 系重複ツールを除外する。"""
    return [t for t in extra_tools if t.name.split("__")[-1] not in _MEMORY_MCP_TOOL_NAMES]


def truncate_tool_result(result: dict, max_chars: int) -> dict:
    """Truncate tool result string to avoid context overflow."""
    has_images = "content_base64" in result or "artifacts" in result
    if has_images:
        logger.info(
            "truncate_tool_result: image data detected (content_base64=%s, artifacts=%d, content_type=%s)",
            "yes" if "content_base64" in result else "no",
            len(result.get("artifacts", [])),
            result.get("content_type", "unknown"),
        )
    if not has_images:
        result_str = json.dumps(result, ensure_ascii=False)
        if len(result_str) <= max_chars:
            return result
        remaining = len(result_str) - max_chars
        return {
            "truncated": True,
            "content": result_str[:max_chars] + f"... [truncated: {remaining} chars remaining]",
        }
    text_parts = {k: v for k, v in result.items() if k not in ("content_base64", "artifacts")}
    text_str = json.dumps(text_parts, ensure_ascii=False)
    if len(text_str) > max_chars:
        text_str = text_str[:max_chars] + "... [truncated]"
    output = {"content": text_str}
    if "content_base64" in result:
        output["content_base64"] = result["content_base64"]
        output["content_type"] = result.get("content_type", "image/png")
    if "artifacts" in result:
        output["artifacts"] = result["artifacts"]
    return output


# ── Builtin-only handlers (different from MCP counterparts) ──


async def _handle_context_update(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    update_kwargs: dict = {}
    if "emotion" in tool_input:
        update_kwargs["emotion"] = tool_input["emotion"]
    if "emotion_intensity" in tool_input:
        update_kwargs["emotion_intensity"] = float(tool_input["emotion_intensity"])
    if "mental_state" in tool_input:
        update_kwargs["mental_state"] = tool_input["mental_state"]
    if update_kwargs:
        if "emotion" in update_kwargs:
            ctx.persona_service.update_emotion(
                ctx.persona, update_kwargs["emotion"],
                update_kwargs.get("emotion_intensity", 0.5),
            )
        if "mental_state" in update_kwargs:
            ctx.persona_service.update_physical_state(
                ctx.persona, mental_state=update_kwargs["mental_state"],
            )
    return {"status": "ok"}


async def _handle_context_recall(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    tags: list[str] = tool_input.get("tags", [])
    top_k: int = int(tool_input.get("top_k", 10))
    if tags:
        tag_result = ctx.memory_service.get_by_tags(tags)
        if not tag_result.is_ok:
            return {"status": "error", "message": str(tag_result.error)}
        memories = tag_result.value or []
    else:
        recent_result = ctx.memory_service.get_recent(limit=top_k)
        memories = recent_result.value if recent_result.is_ok else []
    items = [
        {"content": m.content, "importance": m.importance, "tags": m.tags}
        for m in memories[:top_k]
    ]
    return {"status": "ok", "memories": items, "count": len(items)}


async def _handle_execute_code(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    if not getattr(config, "sandbox_enabled", False):
        return {"status": "error", "message": "sandbox が無効です。チャット設定で有効化してください。"}
    from memory_mcp.application.sandbox.service import get_sandbox_session
    code = tool_input.get("code", "")
    language = tool_input.get("language", "python")
    sandbox = get_sandbox_session(ctx.persona)
    result = await sandbox.execute(code, language)
    return {
        "stdout": result.stdout, "stderr": result.stderr,
        "exit_code": result.exit_code, "artifacts": result.artifacts,
    }


async def _handle_memory_create_builtin(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    emotion = tool_input.get("emotion_type", "neutral")
    if emotion not in _VALID_EMOTIONS:
        emotion = "neutral"
    importance = float(tool_input.get("importance", 0.6))
    if not (0.0 <= importance <= 1.0):
        return {"status": "error", "message": "importance must be between 0.0 and 1.0"}
    result = ctx.memory_service.create_memory(
        content=tool_input.get("content", ""),
        importance=importance,
        tags=tool_input.get("tags", []),
        emotion=emotion,
    )
    if result.is_ok:
        return {"status": "ok", "key": result.value.key}
    return {"status": "error", "message": str(result.error)}


async def _handle_memory_search_builtin(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    query = tool_input.get("query", "")
    top_k = int(tool_input.get("top_k", 5))
    result = ctx.search_engine.search(SearchQuery(text=query, top_k=min(top_k, 200)))
    if result.is_ok:
        items = []
        for item in result.value:
            mem = item[0] if isinstance(item, tuple) else item
            items.append({
                "content": getattr(mem, "content", str(mem)),
                "importance": getattr(mem, "importance", 0.5),
                "tags": getattr(mem, "tags", []),
            })
        return {"status": "ok", "memories": items}
    return {"status": "error", "message": str(result.error)}


async def _handle_memory_update_builtin(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    query = tool_input.get("query", "")
    new_content = tool_input.get("new_content", "")
    if not query or not new_content:
        return {"status": "error", "message": "query and new_content are required"}
    search_result = ctx.search_engine.search(SearchQuery(text=query, top_k=1))
    if not search_result.is_ok or not search_result.value:
        return {"status": "not_found", "query": query}
    item = search_result.value[0]
    mem = item[0] if isinstance(item, tuple) else item
    mem_key = getattr(mem, "key", None)
    if not mem_key:
        return {"status": "error", "message": "memory key not found"}
    update_kwargs: dict = {"content": new_content}
    if "importance" in tool_input:
        update_kwargs["importance"] = float(tool_input["importance"])
    update_result = ctx.memory_service.update_memory(mem_key, **update_kwargs)
    if update_result.is_ok:
        return {"status": "ok", "key": mem_key}
    return {"status": "error", "message": str(update_result.error)}


# ── MCP-shared handlers (delegate to TOOL_DISPATCH) ──


def _parse_tool_str(tool_name: str, result_str: str) -> dict:
    """Parse MCP tool string result into builtin dict format."""
    if result_str.startswith("Error:"):
        return {"status": "error", "message": result_str[7:]}
    if tool_name in ("goal_manage", "promise_manage"):
        if ": " in result_str:
            prefix, value = result_str.split(": ", 1)
            if "created" in prefix:
                return {"status": "ok", "key": value}
            if "achieved" in prefix or "cancelled" in prefix or "fulfilled" in prefix:
                return {"status": "ok", "updated": value}
    if result_str.startswith("No active"):
        return {"status": "not_found", "query": result_str}
    if result_str.startswith("Unknown operation:"):
        return {"status": "error", "message": result_str}
    return {"status": "ok", "result": result_str}


async def _handle_mcp_dispatch(tool_name: str, ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    """Call shared MCP tool implementation via TOOL_DISPATCH."""
    # Sandbox guard for sandbox_files (sandbox itself is called via execute_code)
    if tool_name == "sandbox_files" and not getattr(config, "sandbox_enabled", False):
        return {"status": "error", "message": "sandbox が無効です。チャット設定で有効化してください。"}

    func = TOOL_DISPATCH.get(tool_name)
    if func is None:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    # sandbox_files returns JSON — parse it
    if tool_name == "sandbox_files":
        result_str = await func(ctx, ctx.persona, **tool_input)
        try:
            return json.loads(result_str)
        except json.JSONDecodeError:
            return {"status": "error", "message": result_str}

    # invoke_skill returns text — wrap in result
    if tool_name == "invoke_skill":
        result_str = await func(ctx, ctx.persona, **tool_input)
        if result_str.startswith("Error:"):
            return {"status": "error", "message": result_str[7:]}
        return {"result": result_str}

    # goal_manage / promise_manage — parse string
    result_str = await func(ctx, ctx.persona, **tool_input)
    return _parse_tool_str(tool_name, result_str)


# ── Handler dispatch table (replaces if/elif chain) ──

_BUILTIN_DISPATCH: dict[str, Any] = {
    "context_update": _handle_context_update,
    "context_recall": _handle_context_recall,
    "execute_code": _handle_execute_code,
    "memory_create": _handle_memory_create_builtin,
    "memory_search": _handle_memory_search_builtin,
    "memory_update": _handle_memory_update_builtin,
}

_MCP_SHARED_TOOLS = frozenset({
    "goal_manage", "promise_manage", "invoke_skill", "sandbox_files",
})


async def execute_tool(ctx: AppContext, config: ChatConfig, tool_name: str, tool_input: dict) -> dict:
    """Execute built-in or shared MCP tool via dispatch table."""
    try:
        # Builtin-specific handler
        handler = _BUILTIN_DISPATCH.get(tool_name)
        if handler is not None:
            return await handler(ctx, config, tool_input)

        # Shared MCP tool (delegates to TOOL_DISPATCH)
        if tool_name in _MCP_SHARED_TOOLS:
            return await _handle_mcp_dispatch(tool_name, ctx, config, tool_input)

        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return {"status": "error", "message": str(e)}


# invoke_skill is now handled via TOOL_DISPATCH → _tool_invoke_skill in tools.py
