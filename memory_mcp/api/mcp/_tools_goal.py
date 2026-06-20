"""Auto-generated from tools.py split — _tools_goal.py."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP  # noqa: TC002

from memory_mcp.api.mcp.middleware import get_current_persona
from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.domain.shared.time_utils import get_now, relative_time_str

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.persona.entities import PersonaState


async def _tool_goal_manage(
    ctx: AppContext,
    persona: str,
    operation: str,
    content: str,
    importance: float = 0.75,
    memory_key: str | None = None,
) -> dict:
    if operation == "create":
        result = ctx.memory_service.create_memory(
            content=content,
            importance=importance,
            tags=["goal", "active"],
            emotion="neutral",
        )
        if result.is_ok:
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "goal_manage",
                    "params_summary": f"operation=create, content={content[:50]}",
                    "result_summary": f"Goal created: {result.value.key}",
                    "success": True,
                },
            )
            return {"ok": True, "key": result.value.key}
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "goal_manage",
                "params_summary": f"operation=create, content={content[:50]}",
                "result_summary": str(result.error),
                "success": False,
            },
        )
        return {"ok": False, "error": result.error}
    elif operation in ("achieve", "cancel"):
        new_status = "achieved" if operation == "achieve" else "cancelled"
        if memory_key and memory_key.strip():
            get_result = ctx.memory_service.get_memory(memory_key)
            if not get_result.is_ok:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "goal_manage",
                        "params_summary": f"operation={operation}, memory_key={memory_key}",
                        "result_summary": str(get_result.error),
                        "success": False,
                    },
                )
                return {"ok": False, "error": get_result.error}
            match = get_result.value
            if "goal" not in match.tags or "active" not in match.tags:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "goal_manage",
                        "params_summary": f"operation={operation}, memory_key={memory_key}",
                        "result_summary": f"Memory '{memory_key}' is not an active goal",
                        "success": False,
                    },
                )
                return {"ok": False, "error": f"Memory '{memory_key}' is not an active goal."}
        else:
            tag_result = ctx.memory_service.get_by_tags(["goal", "active"])
            if not tag_result.is_ok:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "goal_manage",
                        "params_summary": f"operation={operation}, content={content[:50]}",
                        "result_summary": str(tag_result.error),
                        "success": False,
                    },
                )
                return {"ok": False, "error": tag_result.error}
            candidates = tag_result.value or []
            match = next((m for m in candidates if content.strip().lower() == m.content.strip().lower()), None)
            if match is None:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "goal_manage",
                        "params_summary": f"operation={operation}, content={content[:50]}",
                        "result_summary": f"No active goal matching '{content[:40]}' found",
                        "success": False,
                    },
                )
                return {"ok": False, "error": f"No active goal matching '{content}' found."}
        new_importance = max(match.importance, 0.9)
        new_tags = ["goal", new_status, "archived"]
        update_result = ctx.memory_service.update_memory(match.key, importance=new_importance, tags=new_tags)
        if update_result.is_ok:
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "goal_manage",
                    "params_summary": f"operation={operation}, content={match.content[:50]}",
                    "result_summary": f"Goal {new_status}: {match.content[:80]}",
                    "success": True,
                },
            )
            return {"ok": True, "status": new_status, "content": match.content[:80]}
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "goal_manage",
                "params_summary": f"operation={operation}, memory_key={match.key}",
                "result_summary": str(update_result.error),
                "success": False,
            },
        )
        return {"ok": False, "error": update_result.error}
    else:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "goal_manage",
                "params_summary": f"operation={operation}, content={content[:50]}",
                "result_summary": f"Unknown operation: {operation}",
                "success": False,
            },
        )
        return {"ok": False, "error": f"Unknown operation: {operation}. Use create/achieve/cancel."}


async def _tool_promise_manage(
    ctx: AppContext,
    persona: str,
    operation: str,
    content: str,
    importance: float = 0.8,
    memory_key: str | None = None,
) -> dict:
    if operation == "create":
        result = ctx.memory_service.create_memory(
            content=content,
            importance=importance,
            tags=["promise", "active"],
            emotion="neutral",
        )
        if result.is_ok:
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "promise_manage",
                    "params_summary": f"operation=create, content={content[:50]}",
                    "result_summary": f"Promise created: {result.value.key}",
                    "success": True,
                },
            )
            return {"ok": True, "key": result.value.key}
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "promise_manage",
                "params_summary": f"operation=create, content={content[:50]}",
                "result_summary": str(result.error),
                "success": False,
            },
        )
        return {"ok": False, "error": result.error}
    elif operation in ("fulfill", "cancel"):
        new_status = "fulfilled" if operation == "fulfill" else "cancelled"
        if memory_key and memory_key.strip():
            get_result = ctx.memory_service.get_memory(memory_key)
            if not get_result.is_ok:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "promise_manage",
                        "params_summary": f"operation={operation}, memory_key={memory_key}",
                        "result_summary": str(get_result.error),
                        "success": False,
                    },
                )
                return {"ok": False, "error": get_result.error}
            match = get_result.value
            if "promise" not in match.tags or "active" not in match.tags:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "promise_manage",
                        "params_summary": f"operation={operation}, memory_key={memory_key}",
                        "result_summary": f"Memory '{memory_key}' is not an active promise",
                        "success": False,
                    },
                )
                return {"ok": False, "error": f"Memory '{memory_key}' is not an active promise."}
        else:
            tag_result = ctx.memory_service.get_by_tags(["promise", "active"])
            if not tag_result.is_ok:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "promise_manage",
                        "params_summary": f"operation={operation}, content={content[:50]}",
                        "result_summary": str(tag_result.error),
                        "success": False,
                    },
                )
                return {"ok": False, "error": tag_result.error}
            candidates = tag_result.value or []
            match = next((m for m in candidates if content.strip().lower() == m.content.strip().lower()), None)
            if match is None:
                await ctx.event_bus.publish(
                    "tool.called",
                    {
                        "persona": persona,
                        "tool_name": "promise_manage",
                        "params_summary": f"operation={operation}, content={content[:50]}",
                        "result_summary": f"No active promise matching '{content[:40]}' found",
                        "success": False,
                    },
                )
                return {"ok": False, "error": f"No active promise matching '{content}' found."}
        new_importance = max(match.importance, 0.9)
        new_tags = ["promise", new_status, "archived"]
        update_result = ctx.memory_service.update_memory(match.key, importance=new_importance, tags=new_tags)
        if update_result.is_ok:
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "promise_manage",
                    "params_summary": f"operation={operation}, content={match.content[:50]}",
                    "result_summary": f"Promise {new_status}: {match.content[:80]}",
                    "success": True,
                },
            )
            return {"ok": True, "status": new_status, "content": match.content[:80]}
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "promise_manage",
                "params_summary": f"operation={operation}, memory_key={match.key}",
                "result_summary": str(update_result.error),
                "success": False,
            },
        )
        return {"ok": False, "error": update_result.error}
    else:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "promise_manage",
                "params_summary": f"operation={operation}, content={content[:50]}",
                "result_summary": f"Unknown operation: {operation}",
                "success": False,
            },
        )
        return {"ok": False, "error": f"Unknown operation: {operation}. Use create/fulfill/cancel."}


