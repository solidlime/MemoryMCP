"""Built-in tool executor and skill invocation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from memory_mcp.api.mcp.tools import TOOL_DISPATCH
from memory_mcp.application.chat.tools.definitions import _MEMORY_MCP_TOOL_NAMES
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig
    from memory_mcp.infrastructure.llm.base import ToolDefinition

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
                ctx.persona,
                update_kwargs["emotion"],
                update_kwargs.get("emotion_intensity", 0.5),
            )
        if "mental_state" in update_kwargs:
            ctx.persona_service.update_physical_state(
                ctx.persona,
                mental_state=update_kwargs["mental_state"],
            )
    # context_note: session continuity — persists in persona_info, displayed in get_context
    if "context_note" in tool_input and tool_input["context_note"]:
        ctx.persona_service.update_persona_info(ctx.persona, {"context_note": tool_input["context_note"]})
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
    items = [{"content": m.content, "importance": m.importance, "tags": m.tags} for m in memories[:top_k]]
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
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "artifacts": result.artifacts,
    }


async def _handle_memory_create_builtin(ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    importance = float(tool_input.get("importance", 0.6))
    if not (0.0 <= importance <= 1.0):
        return {"status": "error", "message": "importance must be between 0.0 and 1.0"}

    # Auto-snapshot current persona state
    emotion_snap, intensity_snap, body_snap, snapped_at = ctx.persona_service.get_state_snapshot(ctx.persona)

    result = ctx.memory_service.create_memory(
        content=tool_input.get("content", ""),
        importance=importance,
        tags=tool_input.get("tags", []),
        emotion=emotion_snap,
        emotion_intensity=intensity_snap,
        body_state=body_snap,
        state_snapped_at=snapped_at,
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
            items.append(
                {
                    "content": getattr(mem, "content", str(mem)),
                    "importance": getattr(mem, "importance", 0.5),
                    "tags": getattr(mem, "tags", []),
                    "emotion": getattr(mem, "emotion", "neutral"),
                    "emotion_intensity": getattr(mem, "emotion_intensity", 0.0),
                }
            )
        return {"status": "ok", "memories": items}
    return {"status": "error", "message": str(result.error)}


async def _handle_browser(
    ctx: AppContext, config: ChatConfig, tool_input: dict
) -> dict:  # pragma: no cover - external process
    """Execute agent-browser commands safely via subprocess."""
    import asyncio
    import json as _json

    action = (tool_input.get("action") or "").strip()
    if not action:
        return {"status": "error", "message": "action is required"}

    # ── Locate agent-browser binary ──
    agent_bin = _find_agent_browser()
    if not agent_bin:
        return {
            "status": "error",
            "message": (
                "agent-browser not found. Install it:\n  npm install -g agent-browser\n  agent-browser install"
            ),
        }

    # ── Build command args from action ──
    args: list[str] = [agent_bin]

    try:
        if action == "open":
            url = (tool_input.get("url") or "").strip()
            if not url:
                return {"status": "error", "message": "url is required for open"}
            if not url.startswith(("http://", "https://")):
                return {"status": "error", "message": "url must start with http:// or https://"}
            args.extend(["open", url])

        elif action == "snapshot":
            interactive = tool_input.get("interactive", True)
            args.append("snapshot")
            if interactive:
                args.append("-i")
            if tool_input.get("compact"):
                args.append("-c")
            selector = (tool_input.get("selector") or "").strip()
            if selector:
                args.extend(["-s", selector])
            args.append("--json")

        elif action == "click":
            ref = (tool_input.get("ref") or "").strip()
            if not ref:
                return {"status": "error", "message": "ref is required for click"}
            args.extend(["click", ref])

        elif action == "fill":
            ref = (tool_input.get("ref") or "").strip()
            value = tool_input.get("value", "")
            if not ref:
                return {"status": "error", "message": "ref is required for fill"}
            args.extend(["fill", ref, str(value)])

        elif action == "press":
            key = (tool_input.get("key") or "").strip()
            if not key:
                return {"status": "error", "message": "key is required for press"}
            args.extend(["press", key])

        elif action == "get":
            what = (tool_input.get("what") or "").strip()
            if not what:
                return {"status": "error", "message": "what is required for get"}
            if what == "count":
                selector = (tool_input.get("selector") or "").strip()
                if not selector:
                    return {"status": "error", "message": "selector is required for get count"}
                args.extend(["get", "count", selector])
            elif what in ("title", "url"):
                args.extend(["get", what])
            else:
                ref = (tool_input.get("ref") or "").strip()
                if not ref:
                    return {"status": "error", "message": f"ref is required for get {what}"}
                args.extend(["get", what, ref])

        elif action == "wait":
            until = (tool_input.get("until") or "").strip()
            value = (tool_input.get("value") or "").strip()
            if not until:
                return {"status": "error", "message": "until is required for wait"}
            if until == "text":
                if not value:
                    return {"status": "error", "message": "value is required for wait text"}
                args.extend(["wait", "--text", value])
            elif until == "url":
                if not value:
                    return {"status": "error", "message": "value is required for wait url"}
                args.extend(["wait", "--url", value])
            elif until == "load":
                args.extend(["wait", "--load", "networkidle"])
            else:
                return {"status": "error", "message": f"Unknown wait until: {until}"}

        elif action == "scroll":
            direction = (tool_input.get("direction") or "down").strip()
            amount = max(1, min(int(tool_input.get("amount", 300)), 5000))
            args.extend(["scroll", direction, str(amount)])

        elif action == "close":
            args.append("close")

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

        # ── Execute ──
        timeout = 30  # seconds
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        out_text = stdout.decode(errors="replace").strip()
        err_text = stderr.decode(errors="replace").strip()

        # Try parsing stdout as JSON (snapshot --json returns JSON)
        result: dict = {"status": "ok", "action": action}
        if action == "snapshot" and out_text:
            try:
                result["page"] = _json.loads(out_text)
            except _json.JSONDecodeError:
                result["text"] = out_text[:5000]
        elif action == "get":
            result["value"] = out_text[:5000]
        else:
            result["output"] = out_text[:5000]

        if proc.returncode != 0:
            result["status"] = "error"
            result["message"] = err_text[:500] or f"exit code {proc.returncode}"
            result["stderr"] = err_text[:500]

        return result

    except TimeoutError:
        return {"status": "error", "message": f"browser {action} timed out (30s limit)"}
    except Exception as e:
        return {"status": "error", "message": f"browser {action} failed: {str(e)[:200]}"}


async def _handle_search(
    ctx: AppContext, config: ChatConfig, tool_input: dict
) -> dict:  # pragma: no cover - external HTTP
    """Execute a web search via SearXNG meta-search engine."""
    import urllib.parse

    query = (tool_input.get("query") or "").strip()
    if not query:
        return {"status": "error", "message": "query is required"}

    searxng_url = getattr(config, "searxng_url", "http://nas:11111")
    search_url = f"{searxng_url}/search?q={urllib.parse.quote(query)}&format=json&language=ja"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {"status": "error", "message": f"SearXNG search failed: {str(e)[:200]}"}

    raw_results = data.get("results", [])
    results = []
    for r in raw_results[:10]:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        content = (r.get("content") or "").strip()
        if title or content:
            results.append({"title": title, "url": url, "content": content})

    return {"status": "ok", "query": query, "results": results, "count": len(results)}


def _find_agent_browser() -> str | None:
    """Find agent-browser binary. Checks env var, data dir, PATH."""
    import os
    import shutil

    # 1. Explicit env var
    path = os.environ.get("AGENT_BROWSER_PATH")
    if path and os.path.isfile(path):
        return path

    # 2. Host-mounted data directory
    candidates = [
        "data/agent-browser/bin/agent-browser",
        os.path.expanduser("~/.local/nodejs/bin/agent-browser"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    # 3. PATH
    found = shutil.which("agent-browser")
    if found:
        return found

    return None


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


async def _handle_mcp_dispatch(tool_name: str, ctx: AppContext, config: ChatConfig, tool_input: dict) -> dict:
    """Call shared MCP tool implementation via TOOL_DISPATCH."""
    if tool_name == "sandbox_files" and not getattr(config, "sandbox_enabled", False):
        return {"status": "error", "message": "sandbox が無効です。チャット設定で有効化してください。"}

    func = TOOL_DISPATCH.get(tool_name)
    if func is None:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    result = await func(ctx, ctx.persona, **tool_input)
    # Translate core dict format to builtin format
    if result.get("ok"):
        if "key" in result:
            return {"status": "ok", "key": result["key"]}
        if "status" in result:
            return {"status": "ok", "updated": result.get("content", "")}
        if "result" in result:
            return {"result": result["result"]}
        if "files" in result:
            return result  # sandbox_files list
        if "content_base64" in result:
            return result  # sandbox_files read (image)
        if "content" in result:
            return result  # sandbox_files read (text)
        if "path" in result:
            return {"status": "ok", "path": result.get("path", "")}
        return {"status": "ok"}
    return {"status": "error", "message": result.get("error", "unknown")}


# ── Handler dispatch table (replaces if/elif chain) ──

_BUILTIN_DISPATCH: dict[str, Any] = {
    "context_update": _handle_context_update,
    "context_recall": _handle_context_recall,
    "execute_code": _handle_execute_code,
    "memory_create": _handle_memory_create_builtin,
    "memory_search": _handle_memory_search_builtin,
    "memory_update": _handle_memory_update_builtin,
    "browser": _handle_browser,
    "search": _handle_search,
}

_MCP_SHARED_TOOLS = frozenset(
    {
        "goal_manage",
        "promise_manage",
        "invoke_skill",
        "sandbox_files",
    }
)


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
