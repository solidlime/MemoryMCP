"""ChatService: チャットのメインロジック・SSEストリーミング。"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from memory_mcp.application.chat.memory_llm import run_memory_llm
from memory_mcp.application.chat.session_store import SessionManager
from memory_mcp.application.chat.tools import MEMORY_TOOLS, _truncate_tool_result, execute_tool, filter_extra_tools
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.domain.shared.time_utils import get_now, relative_time_str
from memory_mcp.infrastructure.llm.base import LLMMessage
from memory_mcp.infrastructure.llm.factory import get_provider
from memory_mcp.infrastructure.logging.structured import get_logger
from memory_mcp.infrastructure.mcp_client import MCPClientPool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

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
            result = ctx.search_engine.search(SearchQuery(text=q, top_k=top_k))
            return result.value if result.is_ok else []
        except Exception as e:
            logger.warning("search_memory failed (query=%s): %s", q[:40], e)
            return []

    results = await asyncio.gather(*[_run(q) for q in queries])

    seen: set[str] = set()
    merged: list = []
    rank_scores: dict[str, float] = {}
    for _rank_idx, result_list in enumerate(results):
        for pos, item in enumerate(result_list):
            if isinstance(item, tuple):
                mem = item[0]
            elif hasattr(item, "memory"):
                mem = item.memory
            else:
                mem = item
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
    lines = [f"- [{getattr(m, 'importance', 0.5):.1f}] {getattr(m, 'content', str(m))}" for m, _ in top]
    debug_results = [
        {
            "content": getattr(m, "content", str(m)),
            "importance": round(float(getattr(m, "importance", 0.5)), 2),
            "score": round(rank_scores.get(getattr(m, "content", str(m)), 0.0), 4),
        }
        for m, _ in top
    ]
    return "\n".join(lines), {"queries": queries, "results": debug_results}


def _sse(event_type: str, data: dict) -> str:
    def _default(obj):
        try:
            return str(obj)
        except Exception:
            return "<not serializable>"

    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False, default=_default)
    return f"data: {payload}\n\n"


def _format_state_summary(state) -> str:
    """PersonaState から簡潔なサマリーを生成する。(後方互換のため残す)"""
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


async def _build_context_section(ctx: AppContext, state) -> str:
    """get_context() 同等の充実したコンテキストサマリーを構築する (T30/T40)。"""
    parts: list[str] = []

    last_conv = getattr(state, "last_conversation_time", None)
    if last_conv:
        time_since = relative_time_str(last_conv)
        parts.append(f"前回の会話: {time_since}")

    if getattr(state, "emotion", None):
        intensity = getattr(state, "emotion_intensity", 0.5)
        parts.append(f"感情: {state.emotion} (強度: {intensity:.1f})")
    if getattr(state, "mental_state", None):
        parts.append(f"精神状態: {state.mental_state}")
    if getattr(state, "physical_state", None):
        parts.append(f"身体状態: {state.physical_state}")
    if getattr(state, "environment", None):
        parts.append(f"環境: {state.environment}")
    if getattr(state, "speech_style", None):
        parts.append(f"話し方: {state.speech_style}")
    if getattr(state, "relationship_status", None):
        parts.append(f"関係性: {state.relationship_status}")

    user_info = getattr(state, "user_info", None) or {}
    if user_info:
        ui_lines = "\n".join(f"  {k}: {v}" for k, v in user_info.items())
        parts.append(f"ユーザー情報:\n{ui_lines}")

    _hidden = {"goals", "promises", "active_promises", "current_goals"}
    persona_info = getattr(state, "persona_info", None) or {}
    filtered_pi = {k: v for k, v in persona_info.items() if k not in _hidden}
    if filtered_pi:
        pi_lines = "\n".join(f"  {k}: {v}" for k, v in filtered_pi.items())
        parts.append(f"ペルソナ情報:\n{pi_lines}")

    try:
        goals_result = ctx.memory_service.get_by_tags(["goal"])
        goals = goals_result.value if goals_result.is_ok else []
        active_goals = [g for g in goals if "active" in (g.tags or [])]

        promises_result = ctx.memory_service.get_by_tags(["promise"])
        promises = promises_result.value if promises_result.is_ok else []
        active_promises = [p for p in promises if "active" in (p.tags or [])]

        if active_goals or active_promises:
            commit_lines: list[str] = []
            for g in active_goals:
                commit_lines.append(f"  🎯 [Goal] {g.content}")
            for p in active_promises:
                commit_lines.append(f"  🤝 [Promise] {p.content}")
            parts.append("アクティブなコミットメント:\n" + "\n".join(commit_lines))
    except Exception as e:
        logger.debug("Failed to fetch goals/promises: %s", e)

    try:
        equip_result = ctx.equipment_service.get_equipment()
        if equip_result.is_ok:
            equipped = {k: v for k, v in equip_result.value.items() if v}
            if equipped:
                equip_lines = "\n".join(f"  {slot}: {item}" for slot, item in equipped.items())
                parts.append(f"装備:\n{equip_lines}")
    except Exception as e:
        logger.debug("Failed to fetch equipment: %s", e)

    return "\n".join(parts)


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

        # 1. セッションウィンドウ
        db = ctx.connection.get_memory_db()
        session = _session_manager.get_or_create(persona, session_id, config.max_window_turns, db=db)
        last_assistant = session.get_last_assistant_content()

        # 2. コンテキスト取得 + 記憶検索（並行実行）
        context_section = ""
        related_memories = ""
        memory_debug: dict = {"queries": [], "results": []}

        pending_payload = session.pop_pending()
        memory_llm_task = None
        if pending_payload and config.auto_extract:
            memory_llm_task = asyncio.create_task(run_memory_llm(ctx, config, pending_payload))

        state_raw: dict = {}
        try:
            state_result = ctx.persona_service.get_context(persona)
            if state_result.is_ok:
                context_section = await _build_context_section(ctx, state_result.value)
                state_obj = state_result.value
                state_raw = (
                    {
                        k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v
                        for k, v in vars(state_obj).items()
                    }
                    if hasattr(state_obj, "__dict__")
                    else {}
                )
        except Exception as e:
            logger.warning("get_context failed: %s", e)

        memories_raw: list[dict] = []
        try:
            related_memories, memory_debug = await _search_memories(ctx, user_message, last_assistant, top_k=8)
            memories_raw = memory_debug.get("results", [])
        except Exception as e:
            logger.warning("_search_memories failed: %s", e)

        memory_llm_result: dict | None = None
        if memory_llm_task is not None:
            try:
                memory_llm_result = await memory_llm_task
            except Exception as e:
                logger.warning("MemoryLLM task error: %s", e)

        # 3. system prompt 構築
        base_system = config.system_prompt or f"あなたは{persona}という名前のアシスタントです。"
        jst_now = now.strftime("%Y-%m-%d %H:%M JST")
        system_parts = [base_system, f"\n現在時刻: {jst_now}"]
        if context_section:
            system_parts.append(f"\n--- ペルソナ状態・コンテキスト ---\n{context_section}")
        if related_memories:
            system_parts.append(f"\n--- 関連記憶 ---\n{related_memories}")
        skills_raw: list[dict] = []
        if config.enabled_skills:
            from memory_mcp.config.settings import get_settings
            from memory_mcp.domain.skill import SkillRepository
            from memory_mcp.infrastructure.sqlite.connection import get_global_skills_db

            skill_repo = SkillRepository(get_global_skills_db(get_settings().data_root))
            skills = [skill_repo.get(n) for n in config.enabled_skills]
            skill_lines = [f"- {s.name}: {s.description}" for s in skills if s]
            skills_raw = [s.model_dump() for s in skills if s]
            if skill_lines:
                system_parts.append("\n--- 利用可能なSkill ---\n" + "\n".join(skill_lines))
        system = "\n".join(system_parts)

        debug_data: dict = {
            "session_id": session_id,
            "provider": config.provider,
            "model": config.get_effective_model(),
            "auto_extract": config.auto_extract,
            "window_messages_count": len(session),
            "system_prompt": system,
            "context_state": state_raw,
            "context_summary": context_section,
            "memories_raw": memories_raw,
            "memory_queries": memory_debug.get("queries", []),
            "skills_raw": skills_raw,
            "tools_injected": [],
            "messages_sent": [],
            "tool_calls": [],
            "assistant_response": "",
            "memory_llm_result": memory_llm_result,
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

            base_tools = list(MEMORY_TOOLS) if config.enable_memory_tools else []
            filtered_extra = filter_extra_tools(extra_tools)
            all_tools = base_tools + filtered_extra

            debug_data["tools_injected"] = [{"name": t.name, "description": t.description} for t in all_tools]
            debug_data["messages_sent"] = [
                {"role": m.role, "content": m.content[:500] + "..." if len(m.content or "") > 500 else m.content}
                for m in messages
            ]

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
                        tool_result = await execute_tool(ctx, config, tc.tool_name, tc.tool_input)
                    truncated_result = _truncate_tool_result(tool_result, config.tool_result_max_chars)
                    yield _sse("tool_result", {"name": tc.tool_name, "result": truncated_result, "id": tc.tool_use_id})
                    debug_data["tool_calls"].append(
                        {
                            "name": tc.tool_name,
                            "input": tc.tool_input,
                            "result": truncated_result,
                            "result_raw": tool_result,
                        }
                    )
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

        debug_data["assistant_response"] = full_response

        if config.auto_extract and full_response:
            session.set_pending({"user": user_message, "assistant": full_response})

        try:
            yield _sse("debug_info", debug_data)
        except Exception as e:
            logger.warning("debug_info SSE emit failed: %s", e)
            yield _sse("debug_info", {"error": str(e), "system_prompt": debug_data.get("system_prompt", "")[:500]})
        yield _sse("done", {"message": "completed"})
