"""チャットツール定義・実行・スキル呼び出し。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.infrastructure.llm.base import LLMMessage, ToolDefinition
from memory_mcp.infrastructure.llm.factory import get_provider
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

MEMORY_TOOLS = [
    ToolDefinition(
        name="memory_create",
        description="新しい記憶を作成する。重要な情報・感情・出来事を記録する際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "記憶の内容"},
                "importance": {"type": "number", "description": "重要度 0.0〜1.0", "default": 0.6},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "タグリスト"},
                "emotion_type": {
                    "type": "string",
                    "description": "感情タイプ（joy/sadness/anger/fear/neutral等）",
                    "default": "neutral",
                },
            },
            "required": ["content"],
        },
    ),
    ToolDefinition(
        name="memory_search",
        description="記憶を検索する。ユーザーについての情報・過去の出来事を調べる際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ"},
                "top_k": {"type": "integer", "description": "取得件数（1〜10）", "default": 5},
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="context_update",
        description="ペルソナ自身の感情・状態を更新する。感情が変わった際に使用。",
        input_schema={
            "type": "object",
            "properties": {
                "emotion": {"type": "string", "description": "感情タイプ"},
                "emotion_intensity": {"type": "number", "description": "感情強度 0.0〜1.0"},
                "mental_state": {"type": "string", "description": "精神状態の説明"},
            },
        },
    ),
    ToolDefinition(
        name="invoke_skill",
        description="特定のスキルを専用コンテキストで実行する。複雑な専門タスクをメインの会話から切り離して処理する",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "スキル名"},
                "task": {"type": "string", "description": "スキルへの具体的な指示"},
            },
            "required": ["name", "task"],
        },
    ),
]

# MCPサーバー由来の memory 系ツール名（MEMORY_TOOLS と重複するため除外対象）
_MEMORY_MCP_TOOL_NAMES = {
    "memory",
    "search_memory",
    "get_context",
    "update_context",
    "item",
    "memory_create",
    "memory_search",
    "context_update",
}


def filter_extra_tools(extra_tools: list[ToolDefinition]) -> list[ToolDefinition]:
    """MCP extra ツールから memory 系重複ツールを除外する。"""
    return [t for t in extra_tools if t.name.split("__")[-1] not in _MEMORY_MCP_TOOL_NAMES]


def _truncate_tool_result(result: dict, max_chars: int) -> dict:
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
