from __future__ import annotations

import asyncio
import json
from collections import OrderedDict, deque
from typing import TYPE_CHECKING

from memory_mcp.domain.shared.time_utils import get_now, relative_time_str
from memory_mcp.infrastructure.llm.base import LLMMessage, ToolDefinition
from memory_mcp.infrastructure.llm.factory import get_provider
from memory_mcp.infrastructure.logging.structured import get_logger
from memory_mcp.infrastructure.mcp_client import MCPClientPool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

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

_EXTRACT_PROMPT = """\
以下の会話から、長期記憶として保存すべき重要情報を抽出してください。

【抽出対象】
- ユーザーの好み・嗜好・習慣
- 重要な個人情報（名前・職業・家族など）
- 明示的な記憶要求（「覚えておいて」「忘れないで」等）
- 約束・予定・目標
- 感情的に重要な出来事

【出力形式】
JSON配列のみ。重要な情報がない場合は空配列 []。コメント不要。
[{{"content": "...", "importance": 0.7, "tags": ["preference"]}}]

会話:
[user]: {user_message}
[assistant]: {assistant_response}
"""


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
        for msg, ts in zip(self._messages, self._timestamps, strict=False):
            label = relative_time_str(ts, now)
            result.append(
                LLMMessage(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=ts,
                    time_label=label,
                )
            )
        return result

    def get_last_assistant_content(self) -> str | None:
        """ウィンドウ内の直近アシスタント発言を返す（なければNone）。"""
        for msg in reversed(self._messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return None

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


async def _search_memories(
    ctx: AppContext, user_message: str, last_assistant: str | None, top_k: int = 8
) -> tuple[str, dict]:
    """T08: 2クエリ並行検索 + RRF風マージ。Returns (formatted_str, debug_info)。"""
    queries = [user_message]
    if last_assistant:
        queries.append(last_assistant[:200])

    async def _run(q: str) -> list:
        try:
            result = ctx.search_engine.search(q, top_k=top_k)
            return result.value if result.is_ok else []
        except Exception as e:
            logger.warning("search_memory failed (query=%s): %s", q[:40], e)
            return []

    results = await asyncio.gather(*[_run(q) for q in queries])

    # RRF マージ（重複排除: content文字列で判定）
    seen: set[str] = set()
    merged: list = []
    rank_scores: dict[str, float] = {}
    for _rank_idx, result_list in enumerate(results):
        for pos, item in enumerate(result_list):
            mem = item[0] if isinstance(item, tuple) else item
            content = getattr(mem, "content", str(mem))
            score = 1.0 / (60 + pos + 1)  # RRF k=60
            if content in seen:
                rank_scores[content] = rank_scores.get(content, 0.0) + score
            else:
                seen.add(content)
                merged.append((mem, score))
                rank_scores[content] = rank_scores.get(content, 0.0) + score

    merged.sort(key=lambda x: rank_scores.get(getattr(x[0], "content", str(x[0])), 0.0), reverse=True)
    top = merged[:top_k]

    if not top:
        return "", {"queries": queries, "results": []}
    lines = [
        f"- [{getattr(m, 'importance', 0.5):.1f}] {getattr(m, 'content', str(m))}"
        for m, _ in top
    ]
    debug_results = [
        {
            "content": getattr(m, "content", str(m)),
            "importance": round(float(getattr(m, "importance", 0.5)), 2),
            "score": round(rank_scores.get(getattr(m, "content", str(m)), 0.0), 4),
        }
        for m, _ in top
    ]
    return "\n".join(lines), {"queries": queries, "results": debug_results}


class FactExtractor:
    """T10: ターン終了後にLLMで重要ファクトを抽出する。"""

    async def extract(self, config: ChatConfig, user_message: str, assistant_response: str) -> list[dict]:
        extract_model = config.extract_model.strip() or config.get_effective_model()
        api_key = config.get_effective_api_key()
        if not api_key or not extract_model:
            return []

        try:
            provider = get_provider(
                config.provider,
                api_key,
                extract_model,
                config.get_effective_base_url(),
            )
        except Exception as e:
            logger.warning("FactExtractor: provider init failed: %s", e)
            return []

        prompt = _EXTRACT_PROMPT.format(
            user_message=user_message[:500],
            assistant_response=assistant_response[:500],
        )

        from memory_mcp.infrastructure.llm.base import DoneEvent, ErrorEvent, TextDeltaEvent

        text = ""
        try:
            async for event in provider.stream(
                messages=[LLMMessage(role="user", content=prompt)],
                system="",
                tools=[],
                temperature=0.0,
                max_tokens=config.extract_max_tokens,
            ):
                if isinstance(event, TextDeltaEvent):
                    text += event.content
                elif isinstance(event, (DoneEvent, ErrorEvent)):
                    break
        except Exception as e:
            logger.warning("FactExtractor: LLM call failed: %s", e)
            return []

        return _parse_facts(text)


def _parse_facts(text: str) -> list[dict]:
    """LLM出力からJSON配列をパースする。"""
    text = text.strip()
    # マークダウンコードブロックを除去
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        facts = json.loads(text)
        if isinstance(facts, list):
            return [f for f in facts if isinstance(f, dict) and "content" in f]
    except Exception:
        pass
    return []


async def _run_auto_extract(ctx: AppContext, config: ChatConfig, user_message: str, assistant_response: str) -> None:
    """T11: fire-and-forget 自動ファクト抽出。"""
    try:
        extractor = FactExtractor()
        facts = await extractor.extract(config, user_message, assistant_response)
        for fact in facts:
            ctx.memory_service.create_memory(
                content=fact["content"],
                importance=float(fact.get("importance", 0.6)),
                tags=fact.get("tags", ["auto_extract"]),
                emotion=fact.get("emotion_type", "neutral"),
            )
        if facts:
            logger.info("Auto-extracted %d facts for persona=%s", len(facts), ctx.persona)
    except Exception as e:
        logger.warning("Auto-extract failed: %s", e)


class ChatService:
    async def chat(
        self,
        ctx: AppContext,
        config: ChatConfig,
        session_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        now = get_now()
        persona = ctx.persona

        # 1. セッションウィンドウ（先に取得して検索クエリ拡張に使う）
        session = _session_manager.get_or_create(persona, session_id, config.max_window_turns)
        last_assistant = session.get_last_assistant_content()

        # 2. コンテキスト取得 + 記憶検索（T08: 並行実行）
        context_section = ""
        related_memories = ""
        memory_debug: dict = {"queries": [], "results": []}
        try:
            state_result = ctx.persona_service.get_context(persona)
            if state_result.is_ok:
                context_section = _format_state_summary(state_result.value)
        except Exception as e:
            logger.warning("get_context failed: %s", e)

        try:
            related_memories, memory_debug = await _search_memories(ctx, user_message, last_assistant, top_k=8)
        except Exception as e:
            logger.warning("_search_memories failed: %s", e)

        # 3. system prompt構築
        base_system = config.system_prompt or f"あなたは{persona}という名前のアシスタントです。"
        jst_now = now.strftime("%Y-%m-%d %H:%M JST")
        system_parts = [base_system, f"\n現在時刻: {jst_now}"]
        if context_section:
            system_parts.append(f"\n--- ペルソナ状態・コンテキスト ---\n{context_section}")
        if related_memories:
            system_parts.append(f"\n--- 関連記憶 ---\n{related_memories}")
        if config.enabled_skills:
            from memory_mcp.domain.skill import SkillRepository
            skill_repo = SkillRepository(ctx.connection.get_memory_db())
            skills = [skill_repo.get(n) for n in config.enabled_skills]
            skill_lines = [f"- {s.name}: {s.description}" for s in skills if s]
            if skill_lines:
                system_parts.append("\n--- 利用可能なSkill ---\n" + "\n".join(skill_lines))
        system = "\n".join(system_parts)

        # T26: デバッグデータ収集
        debug_data: dict = {
            "system_prompt": system,
            "memory_queries": memory_debug.get("queries", []),
            "memory_results": memory_debug.get("results", []),
            "context_summary": context_section,
            "tool_calls": [],
        }

        # 4. ウィンドウメッセージ
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

        async with MCPClientPool(config.mcp_servers) as mcp_pool:
            extra_tools = mcp_pool.list_all_tools()
            all_tools = MEMORY_TOOLS + extra_tools

            while tool_call_count <= config.max_tool_calls:
                pending_tool_calls: list[ToolCallEvent] = []
                current_text = ""

                async for event in provider.stream(
                    messages=messages,
                    system=system,
                    tools=all_tools,
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

                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=current_text,
                        tool_calls=[
                            {"id": tc.tool_use_id, "name": tc.tool_name, "input": tc.tool_input}
                            for tc in pending_tool_calls
                        ],
                    )
                )

                for tc in pending_tool_calls:
                    yield _sse("tool_call", {"name": tc.tool_name, "input": tc.tool_input, "id": tc.tool_use_id})
                    if "__" in tc.tool_name:
                        tool_result = await mcp_pool.call_tool(tc.tool_name, tc.tool_input)
                    else:
                        tool_result = await _execute_tool(ctx, config, tc.tool_name, tc.tool_input)
                    truncated_result = _truncate_tool_result(tool_result, config.tool_result_max_chars)
                    yield _sse("tool_result", {"name": tc.tool_name, "result": truncated_result, "id": tc.tool_use_id})
                    debug_data["tool_calls"].append({
                        "name": tc.tool_name,
                        "input": tc.tool_input,
                        "result": truncated_result,
                    })
                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=json.dumps(truncated_result, ensure_ascii=False),
                            tool_call_id=tc.tool_use_id,
                        )
                    )

                tool_call_count += 1

        session.add("user", user_message, now)
        session.add("assistant", full_response, get_now())

        # T11: バックグラウンド自動ファクト抽出（SSEをブロックしない）
        if config.auto_extract and full_response:
            asyncio.create_task(_run_auto_extract(ctx, config, user_message, full_response))

        yield _sse("debug_info", debug_data)
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


async def _execute_tool(ctx: AppContext, config: ChatConfig, tool_name: str, tool_input: dict) -> dict:
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
            return await _invoke_skill(ctx, config, skill_name, task)

        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return {"status": "error", "message": str(e)}


def _sse(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def _invoke_skill(ctx: AppContext, config: ChatConfig, skill_name: str, task: str) -> dict:
    from memory_mcp.domain.skill import SkillRepository
    from memory_mcp.infrastructure.llm.base import DoneEvent, TextDeltaEvent

    skill_repo = SkillRepository(ctx.connection.get_memory_db())
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
