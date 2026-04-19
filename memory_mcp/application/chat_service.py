from __future__ import annotations

import json
from collections import OrderedDict, deque
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING

from memory_mcp.domain.shared.time_utils import get_now, relative_time_str
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
                "emotion_type": {"type": "string", "description": "感情タイプ（joy/sadness/anger/fear/neutral等）", "default": "neutral"},
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
]


class SessionWindow:
    def __init__(self, max_turns: int = 3) -> None:
        max_messages = max_turns * 2
        self._messages: deque[dict] = deque(maxlen=max_messages)
        self._timestamps: deque[datetime] = deque(maxlen=max_messages)

    def add(self, role: str, content: str, ts: datetime | None = None) -> None:
        self._messages.append({"role": role, "content": content})
        self._timestamps.append(ts or get_now())

    def get_labeled_messages(self, now: datetime | None = None) -> list[LLMMessage]:
        if now is None:
            now = get_now()
        result = []
        for msg, ts in zip(self._messages, self._timestamps):
            label = relative_time_str(ts, now)
            result.append(LLMMessage(
                role=msg["role"],
                content=msg["content"],
                timestamp=ts,
                time_label=label,
            ))
        return result

    def __len__(self) -> int:
        return len(self._messages)


class SessionManager:
    def __init__(self, max_sessions: int = 100) -> None:
        self._max = max_sessions
        self._sessions: OrderedDict[tuple[str, str], SessionWindow] = OrderedDict()

    def get_or_create(self, persona: str, session_id: str, max_turns: int = 3) -> SessionWindow:
        key = (persona, session_id)
        if key in self._sessions:
            self._sessions.move_to_end(key)
            return self._sessions[key]
        if len(self._sessions) >= self._max:
            self._sessions.popitem(last=False)
        window = SessionWindow(max_turns=max_turns)
        self._sessions[key] = window
        return window

    def clear(self, persona: str, session_id: str) -> None:
        self._sessions.pop((persona, session_id), None)


_session_manager = SessionManager()


class ChatService:
    async def chat(
        self,
        ctx: "AppContext",
        config: "ChatConfig",
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        now = get_now()
        persona = ctx.persona

        # 1. コンテキスト取得
        context_section = ""
        try:
            state_result = ctx.persona_service.get_context(persona)
            if state_result.is_ok:
                state = state_result.value
                context_section = _format_state_summary(state)
        except Exception as e:
            logger.warning("get_context failed: %s", e)

        # 2. 記憶検索
        related_memories = ""
        try:
            search_result = ctx.search_engine.search(user_message, top_k=5)
            if search_result.is_ok and search_result.value:
                lines = []
                for item in search_result.value:
                    mem = item[0] if isinstance(item, tuple) else item
                    lines.append(f"- [{getattr(mem, 'importance', 0.5):.1f}] {getattr(mem, 'content', str(mem))}")
                related_memories = "\n".join(lines)
        except Exception as e:
            logger.warning("search_memory failed: %s", e)

        # 3. system prompt構築
        base_system = config.system_prompt or f"あなたは{persona}という名前のアシスタントです。"
        jst_now = now.strftime("%Y-%m-%d %H:%M JST")
        system_parts = [base_system, f"\n現在時刻: {jst_now}"]
        if context_section:
            system_parts.append(f"\n--- ペルソナ状態・コンテキスト ---\n{context_section}")
        if related_memories:
            system_parts.append(f"\n--- 関連記憶 ---\n{related_memories}")
        system = "\n".join(system_parts)

        # 4. セッションウィンドウ
        session = _session_manager.get_or_create(persona, session_id, config.max_window_turns)
        window_messages = session.get_labeled_messages(now)

        # 5. プロバイダー初期化
        api_key = config.get_effective_api_key()
        if not api_key:
            yield _sse("error", {"message": "APIキーが設定されていません。チャット設定でAPIキーを入力してください。"})
            return

        try:
            provider = get_provider(
                config.provider,
                api_key,
                config.get_effective_model(),
                config.get_effective_base_url(),
            )
        except Exception as e:
            yield _sse("error", {"message": f"LLMプロバイダーの初期化に失敗: {e}"})
            return

        from memory_mcp.infrastructure.llm.base import DoneEvent, ErrorEvent, TextDeltaEvent, ToolCallEvent

        messages = list(window_messages)
        messages.append(LLMMessage(role="user", content=user_message))
        full_response = ""
        tool_call_count = 0

        while tool_call_count <= config.max_tool_calls:
            pending_tool_calls: list[ToolCallEvent] = []
            current_text = ""

            async for event in provider.stream(
                messages=messages,
                system=system,
                tools=MEMORY_TOOLS,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            ):
                if isinstance(event, TextDeltaEvent):
                    current_text += event.content
                    full_response += event.content
                    yield _sse("text_delta", {"content": event.content})
                elif isinstance(event, ToolCallEvent):
                    pending_tool_calls.append(event)
                elif isinstance(event, DoneEvent):
                    pass
                elif isinstance(event, ErrorEvent):
                    yield _sse("error", {"message": event.message})
                    return

            if not pending_tool_calls:
                break

            messages.append(LLMMessage(
                role="assistant",
                content=current_text,
                tool_calls=[
                    {"id": tc.tool_use_id, "name": tc.tool_name, "input": tc.tool_input}
                    for tc in pending_tool_calls
                ],
            ))

            for tc in pending_tool_calls:
                yield _sse("tool_call", {"name": tc.tool_name, "input": tc.tool_input, "id": tc.tool_use_id})
                tool_result = await _execute_tool(ctx, tc.tool_name, tc.tool_input)
                yield _sse("tool_result", {"name": tc.tool_name, "result": tool_result, "id": tc.tool_use_id})
                messages.append(LLMMessage(
                    role="tool",
                    content=json.dumps(tool_result, ensure_ascii=False),
                    tool_call_id=tc.tool_use_id,
                ))

            tool_call_count += 1

        session.add("user", user_message, now)
        session.add("assistant", full_response, get_now())

        yield _sse("done", {"message": "completed"})


def _format_state_summary(state) -> str:
    """PersonaState から簡潔なサマリーを生成する。"""
    parts = []
    if hasattr(state, "emotion") and state.emotion:
        intensity = getattr(state, "emotion_intensity", 0.5)
        parts.append(f"感情: {state.emotion} (強度: {intensity:.1f})")
    if hasattr(state, "mental_state") and state.mental_state:
        parts.append(f"精神状態: {state.mental_state}")
    if hasattr(state, "physical_state") and state.physical_state:
        parts.append(f"身体状態: {state.physical_state}")
    if hasattr(state, "environment") and state.environment:
        parts.append(f"環境: {state.environment}")
    return "\n".join(parts)


async def _execute_tool(ctx: "AppContext", tool_name: str, tool_input: dict) -> dict:
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
            result = ctx.search_engine.search(query, top_k=min(top_k, 10))
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
                    ctx.persona_service.update_physical_state(
                        ctx.persona, mental_state=update_kwargs["mental_state"]
                    )
            return {"status": "ok"}

        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return {"status": "error", "message": str(e)}


def _sse(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"
