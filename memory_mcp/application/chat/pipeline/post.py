"""PostProcessStep: MemoryLLM await実行 + Reflection SSE + セッション更新 + DebugInfo SSE。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from memory_mcp.application.chat.events import (
    DebugInfoSSE,
    DoneSSE,
    MemoryActivitySSE,
    ReflectionDoneSSE,
    ReflectionStartSSE,
)
from memory_mcp.application.chat.memory_llm import run_context_housekeeping, run_memory_llm
from memory_mcp.application.chat.reflection import maybe_run_reflection
from memory_mcp.application.chat.summarizer import summarize_and_store
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.chat.session_store import SessionWindow
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)


async def _do_summarize(ctx: AppContext, config: ChatConfig, turns: list[dict]) -> None:
    """Fire-and-forget summarization helper."""
    try:
        summary = await summarize_and_store(ctx, config, turns)
        if summary:
            logger.info("Session summarized: %s...", summary[:50])
    except Exception as e:
        logger.warning("_do_summarize error: %s", e)


class PostProcessStep:
    """MemoryLLM await実行 + Reflection SSE + セッション更新 + debug_info/done SSEの送出。"""

    async def run(
        self,
        ctx: AppContext,
        config: ChatConfig,
        session: SessionWindow,
        turn_ctx: ChatTurnContext,
        debug: bool = False,
    ) -> AsyncIterator[DebugInfoSSE | DoneSSE | MemoryActivitySSE | ReflectionStartSSE | ReflectionDoneSSE]:
        # evict_callback を設定してからセッションにターンを追加
        if getattr(config, "session_summarize", True) and getattr(config, "extract_model", ""):

            def _evict_cb(evicted: list[dict]) -> None:
                asyncio.create_task(_do_summarize(ctx, config, evicted))

            session.evict_callback = _evict_cb

        now = get_now()
        session.add("user", turn_ctx.user_message, now)
        session.add("assistant", turn_ctx.full_response, get_now())

        # 最終会話時刻を記録
        try:
            ctx.persona_service.record_conversation_time(ctx.persona)
        except Exception as e:
            logger.warning("PostProcessStep: record_conversation_time failed: %s", e)

        # MemoryLLM: DoneSSE前にawait実行（fire-and-forgetをやめて結果をSSEに含める）
        memory_result: dict = {}
        if config.auto_extract and turn_ctx.full_response:
            payload = {"user": turn_ctx.user_message, "assistant": turn_ctx.full_response}
            try:
                memory_result = await run_memory_llm(ctx, config, payload)
            except Exception as e:
                logger.warning("PostProcessStep: run_memory_llm failed: %s", e)

        # Housekeeping: active goals+promises が threshold 超えたら自動整理
        housekeeping_threshold = getattr(config, "housekeeping_threshold", 10)
        try:
            goal_count = 0
            promise_count = 0
            g_res = ctx.memory_service.get_by_tags(["goal", "active"])
            if g_res.is_ok and g_res.value:
                goal_count = len(g_res.value)
            p_res = ctx.memory_service.get_by_tags(["promise", "active"])
            if p_res.is_ok and p_res.value:
                promise_count = len(p_res.value)
            if goal_count + promise_count >= housekeeping_threshold:
                logger.info(
                    "PostProcessStep: housekeeping triggered (goals=%d, promises=%d, threshold=%d)",
                    goal_count,
                    promise_count,
                    housekeeping_threshold,
                )
                asyncio.create_task(run_context_housekeeping(ctx, config))
        except Exception as e:
            logger.warning("PostProcessStep: housekeeping check failed: %s", e)

        # MemoryActivitySSE: 取得された記憶と保存された記憶・goals・promises を通知
        retrieved_for_sse = turn_ctx.memories_raw[:5]
        saved_facts = [
            {"content": f.get("content", ""), "tags": f.get("tags", [])}
            for f in memory_result.get("facts", [])
            if f.get("content")
        ]
        saved_goals = [{"content": g.get("content", "")} for g in memory_result.get("goals", []) if g.get("content")]
        saved_promises = [
            {"content": p.get("content", "")} for p in memory_result.get("promises", []) if p.get("content")
        ]
        yield MemoryActivitySSE(
            retrieved=retrieved_for_sse,
            saved=saved_facts,
            goals=saved_goals,
            promises=saved_promises,
        )

        # debug_info SSE — only when debug flag is enabled
        if debug:
            debug_data = {
                "session_id": turn_ctx.session_id,
                "provider": config.provider,
                "model": config.get_effective_model(),
                "auto_extract": config.auto_extract,
                "system_prompt": turn_ctx.system_prompt,
                "context_state": turn_ctx.state_raw,
                "context_summary": turn_ctx.context_section,
                "memories_raw": turn_ctx.memories_raw,
                "memory_queries": turn_ctx.memory_debug.get("queries", []),
                "skills_raw": turn_ctx.skills_raw,
                "tools_injected": [],
                "messages_sent": [
                    {"role": m.role, "content": m.content[:500] + "..." if len(m.content or "") > 500 else m.content}
                    for m in turn_ctx.messages
                ],
                "tool_calls": turn_ctx.tool_calls_log,
                "assistant_response": turn_ctx.full_response,
            }
            try:
                yield DebugInfoSSE(data=debug_data)
            except Exception as e:
                logger.warning("PostProcessStep: debug_info SSE failed: %s", e)
                yield DebugInfoSSE(data={"error": str(e), "system_prompt": turn_ctx.system_prompt[:500]})

        yield DoneSSE()

        # Reflection: DoneSSE後にawait実行 & SSE通知
        # importance_sum = 保存された facts の importance 合計 + ツールコール数 * 0.3
        if getattr(config, "reflection_enabled", True):
            importance_sum = (
                sum(float(f.get("importance", 0.6)) for f in memory_result.get("facts", []))
                + len(turn_ctx.tool_calls_log) * 0.3
            )
            threshold = getattr(config, "reflection_threshold", 1.0)
            if importance_sum >= threshold:
                try:
                    yield ReflectionStartSSE()
                    insights = await maybe_run_reflection(ctx, config, importance_sum)
                    yield ReflectionDoneSSE(insights=insights or [])
                except Exception as e:
                    logger.warning("PostProcessStep: reflection failed: %s", e)
                    yield ReflectionDoneSSE(insights=[])
