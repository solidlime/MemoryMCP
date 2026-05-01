"""Built-in tool executor and skill invocation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from memory_mcp.application.chat.tools.definitions import _MEMORY_MCP_TOOL_NAMES
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.infrastructure.llm.base import LLMMessage, ToolDefinition
from memory_mcp.infrastructure.llm.factory import get_provider
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
    result_str = json.dumps(result, ensure_ascii=False)
    if len(result_str) <= max_chars:
        return result
    remaining = len(result_str) - max_chars
    return {
        "truncated": True,
        "content": result_str[:max_chars] + f"... [truncated: {remaining} chars remaining]",
    }


async def execute_tool(ctx: AppContext, config: ChatConfig, tool_name: str, tool_input: dict) -> dict:
    """組み込みツールを実行する。"""
    try:
        if tool_name == "memory_create":
            result = ctx.memory_service.create_memory(
                content=tool_input.get("content", ""),
                importance=float(tool_input.get("importance", 0.6)),
                tags=tool_input.get("tags", []),
                emotion=tool_input.get("emotion_type", "neutral"),
            )
            if result.is_ok:
                return {"status": "ok", "key": result.value.key}
            return {"status": "error", "message": str(result.error)}

        elif tool_name == "memory_search":
            query = tool_input.get("query", "")
            top_k = int(tool_input.get("top_k", 5))
            result = ctx.search_engine.search(SearchQuery(text=query, top_k=min(top_k, 10)))
            if result.is_ok:
                items = []
                for item in result.value:
                    mem = item[0] if isinstance(item, tuple) else item
                    items.append(
                        {
                            "content": getattr(mem, "content", str(mem)),
                            "importance": getattr(mem, "importance", 0.5),
                            "tags": getattr(mem, "tags", []),
                        }
                    )
                return {"status": "ok", "memories": items}
            return {"status": "error", "message": str(result.error)}

        elif tool_name == "context_update":
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
                    ctx.persona_service.update_physical_state(ctx.persona, mental_state=update_kwargs["mental_state"])
            return {"status": "ok"}

        elif tool_name == "invoke_skill":
            skill_name = tool_input.get("name", "")
            task = tool_input.get("task", "")
            return await invoke_skill(ctx, config, skill_name, task)

        elif tool_name == "goal_create":
            result = ctx.memory_service.create_memory(
                content=tool_input.get("content", ""),
                importance=float(tool_input.get("importance", 0.75)),
                tags=["goal", "active"],
                emotion="neutral",
            )
            if result.is_ok:
                return {"status": "ok", "key": result.value.key}
            return {"status": "error", "message": str(result.error)}

        elif tool_name in ("goal_achieve", "goal_cancel"):
            target_content = tool_input.get("content", "").lower()
            new_status = "achieved" if tool_name == "goal_achieve" else "cancelled"
            tag_result = ctx.memory_service.get_by_tags(["goal", "active"])
            if not tag_result.is_ok:
                return {"status": "error", "message": str(tag_result.error)}
            candidates = tag_result.value or []
            match = next(
                (m for m in candidates if target_content in m.content.lower()),
                None,
            )
            if match is None:
                return {"status": "not_found", "query": tool_input.get("content", "")}
            update_result = ctx.memory_service.update_memory(match.key, tags=["goal", new_status])
            if update_result.is_ok:
                return {"status": "ok", "updated": match.content[:80]}
            return {"status": "error", "message": str(update_result.error)}

        elif tool_name == "promise_create":
            result = ctx.memory_service.create_memory(
                content=tool_input.get("content", ""),
                importance=float(tool_input.get("importance", 0.8)),
                tags=["promise", "active"],
                emotion="neutral",
            )
            if result.is_ok:
                return {"status": "ok", "key": result.value.key}
            return {"status": "error", "message": str(result.error)}

        elif tool_name == "promise_fulfill":
            target_content = tool_input.get("content", "").lower()
            tag_result = ctx.memory_service.get_by_tags(["promise", "active"])
            if not tag_result.is_ok:
                return {"status": "error", "message": str(tag_result.error)}
            candidates = tag_result.value or []
            match = next(
                (m for m in candidates if target_content in m.content.lower()),
                None,
            )
            if match is None:
                return {"status": "not_found", "query": tool_input.get("content", "")}
            update_result = ctx.memory_service.update_memory(match.key, tags=["promise", "fulfilled"])
            if update_result.is_ok:
                return {"status": "ok", "updated": match.content[:80]}
            return {"status": "error", "message": str(update_result.error)}

        elif tool_name == "memory_update":
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

        elif tool_name == "context_recall":
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
                {
                    "content": m.content,
                    "importance": m.importance,
                    "tags": m.tags,
                }
                for m in memories[:top_k]
            ]
            return {"status": "ok", "memories": items, "count": len(items)}

        elif tool_name == "execute_code":
            if not getattr(config, "sandbox_enabled", False):
                return {"status": "error", "message": "sandbox が無効です。チャット設定で有効化してください。"}
            from memory_mcp.application.sandbox.service import get_sandbox_session

            code = tool_input.get("code", "")
            language = tool_input.get("language", "python")
            docker_host = getattr(config, "sandbox_docker_host", "")
            sandbox = get_sandbox_session(ctx.persona, docker_host)
            result = await sandbox.execute(code, language)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
            }

        elif tool_name == "sandbox_files":
            if not getattr(config, "sandbox_enabled", False):
                return {"status": "error", "message": "sandbox が無効です。チャット設定で有効化してください。"}
            from memory_mcp.application.sandbox.service import get_sandbox_session

            operation = tool_input.get("operation", "")
            path = tool_input.get("path") or "/workspace"
            if not path.startswith("/workspace"):
                return {"status": "error", "message": "パスは /workspace 配下のみ許可されています"}

            docker_host = getattr(config, "sandbox_docker_host", "")
            sandbox = get_sandbox_session(ctx.persona, docker_host)

            if operation == "list":
                files = await sandbox.list_files(path)
                return {
                    "status": "ok",
                    "files": [
                        {"name": f.name, "path": f.path, "is_dir": f.is_dir, "size": f.size}
                        for f in files
                    ],
                }
            elif operation == "read":
                raw = await sandbox.read_file(path)
                MAX_READ = 8192
                truncated = len(raw) > MAX_READ
                text = raw[:MAX_READ].decode("utf-8", errors="replace")
                read_result: dict = {"status": "ok", "content": text}
                if truncated:
                    read_result["truncated"] = True
                    read_result["total_bytes"] = len(raw)
                return read_result
            elif operation == "write":
                import base64

                content_str = tool_input.get("content", "")
                b64 = base64.b64encode(content_str.encode()).decode()
                write_code = (
                    f"import base64, os\n"
                    f"_d = base64.b64decode({b64!r})\n"
                    f"os.makedirs(os.path.dirname({path!r}) or '.', exist_ok=True)\n"
                    f"open({path!r}, 'wb').write(_d)\n"
                    f"print('written', len(_d), 'bytes')"
                )
                exec_result = await sandbox.execute(write_code)
                return {"status": "ok", "path": path, "stdout": exec_result.stdout.strip()}
            elif operation == "delete":
                deleted = await sandbox.delete_file(path)
                return {"status": "ok" if deleted else "error", "path": path}
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return {"status": "error", "message": str(e)}


async def invoke_skill(ctx: AppContext, config: ChatConfig, skill_name: str, task: str) -> dict:
    """スキルを独立コンテキストで実行する。"""
    from memory_mcp.config.settings import get_settings
    from memory_mcp.domain.skill import SkillRepository
    from memory_mcp.infrastructure.llm.base import DoneEvent, TextDeltaEvent
    from memory_mcp.infrastructure.sqlite.connection import get_global_skills_db

    skill_repo = SkillRepository(get_global_skills_db(get_settings().data_root))
    skill = skill_repo.get(skill_name)
    if not skill:
        return {"error": f"Skill '{skill_name}' not found"}

    api_key = config.get_effective_api_key()
    if not api_key:
        return {"error": "APIキーが設定されていません"}

    try:
        provider = get_provider(
            config.provider,
            api_key,
            config.get_effective_model(),
            config.get_effective_base_url(),
        )
    except Exception as e:
        return {"error": f"Provider init failed: {e}"}

    text = ""
    try:
        async for event in provider.stream(
            messages=[LLMMessage(role="user", content=task)],
            system=skill.content,
            tools=[],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        ):
            if isinstance(event, TextDeltaEvent):
                text += event.content
            elif isinstance(event, DoneEvent):
                break
    except Exception as e:
        return {"error": f"Skill execution failed: {e}"}

    return {"result": text or "(no response)"}
