"""PostProcessStep: MemoryLLM fire-and-forget + セッション更新 + DebugInfo SSE。"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from memory_mcp.application.chat.events import DebugInfoSSE, DoneSSE
from memory_mcp.application.chat.memory_llm import run_memory_llm
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.chat.session_store import SessionWindow
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)


class PostProcessStep:
    """MemoryLLM fire-and-forget + セッション更新 + debug_info/done SSEの送出。"""

    async def run(
        self,
        ctx: AppContext,
        config: ChatConfig,
        session: SessionWindow,
        turn_ctx: ChatTurnContext,
        debug: bool = False,
    ) -> AsyncIterator[DebugInfoSSE | DoneSSE]:
        # セッションにターンを追加
        now = get_now()
        session.add("user", turn_ctx.user_message, now)
        session.add("assistant", turn_ctx.full_response, get_now())

        # 最終会話時刻を記録
        try:
            ctx.persona_service.record_conversation_time(ctx.persona)
        except Exception as e:
            logger.warning("PostProcessStep: record_conversation_time failed: %s", e)

        # MemoryLLM を fire-and-forget で起動
        if config.auto_extract and turn_ctx.full_response:
            payload = {"user": turn_ctx.user_message, "assistant": turn_ctx.full_response}
            task = asyncio.create_task(run_memory_llm(ctx, config, payload))
            session.pending_memory_task = task

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
