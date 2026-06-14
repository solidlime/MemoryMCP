"""ChatService: パイプライン型チャットオーケストレーター。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.application.chat.pipeline.compress import CompressStep
from memory_mcp.application.chat.pipeline.context import ChatTurnContext
from memory_mcp.application.chat.pipeline.inference import InferenceStep
from memory_mcp.application.chat.pipeline.post import PostProcessStep
from memory_mcp.application.chat.pipeline.prepare import PrepareStep
from memory_mcp.application.chat.pipeline.prompt import PromptBuildStep
from memory_mcp.application.chat.session_store import SessionManager
from memory_mcp.application.chat.tools.definitions import MEMORY_TOOLS, SANDBOX_TOOLS
from memory_mcp.application.chat.tools.registry import ToolRegistry
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.infrastructure.logging.structured import get_logger
from memory_mcp.infrastructure.mcp_client import MCPClientPool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

_session_manager = SessionManager()


class ChatService:
    async def chat(
        self,
        ctx: AppContext,
        config: ChatConfig,
        session_id: str,
        user_message: str,
        debug: bool = False,
        images: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        persona = ctx.persona
        db = ctx.connection.get_memory_db()
        session = _session_manager.get_or_create(persona, session_id, max_messages=config.max_stored_messages, db=db)

        turn_ctx = ChatTurnContext(session_id=session_id, user_message=user_message, images=images or [])

        # Publish chat.message event for server-side history
        await ctx.event_bus.publish("chat.message", {
            "persona": persona,
            "session_id": session_id,
            "content": user_message,
            "timestamp": get_now().isoformat(),
        })

        # PrepareStep: pending_memory_task 待機 + EmotionDecay + コンテキスト取得
        await PrepareStep().run(ctx, session, turn_ctx, config=config)

        # PromptBuildStep: system プロンプト組み立て
        PromptBuildStep().run(ctx, config, turn_ctx)

        # InferenceStep + PostProcessStep: MCPプール共有
        async with MCPClientPool(config.mcp_servers) as mcp_pool:
            builtin = list(MEMORY_TOOLS) if config.enable_memory_tools else []
            if getattr(config, "sandbox_enabled", False):
                builtin = builtin + list(SANDBOX_TOOLS)
            registry = ToolRegistry(builtin, mcp_pool)

            session_messages = session.get_labeled_messages()

            # CompressStep: コンテキスト圧縮（トークン予算超過時にシステムプロンプト・会話履歴を縮める）
            messages = CompressStep().run(ctx, config, turn_ctx, session_messages)
            # Notify frontend if compression occurred
            comp_info = getattr(turn_ctx, '_compression_info', None)
            if comp_info:
                # Publish compaction event
                await ctx.event_bus.publish("session.compact", {
                    "persona": persona,
                    "session_id": session_id,
                    "before_tokens": comp_info["before_tokens"],
                    "after_tokens": comp_info["after_tokens"],
                    "timestamp": get_now().isoformat(),
                })
                from memory_mcp.application.chat.events import ContextCompressedSSE
                yield ContextCompressedSSE(
                    before_tokens=comp_info["before_tokens"],
                    after_tokens=comp_info["after_tokens"],
                    budget=comp_info["budget"],
                    mode=config.context_compression_mode,
                ).to_sse()

            # Collect and stream LLM response
            full_response = ""
            async for event in InferenceStep().run(ctx, config, messages, turn_ctx, registry):
                yield event.to_sse()
                # Collect text deltas for chat.llm_response event
                from memory_mcp.application.chat.events import TextDeltaSSE
                if isinstance(event, TextDeltaSSE):
                    full_response += event.content

            # Publish chat.llm_response event
            if full_response:
                await ctx.event_bus.publish("chat.llm_response", {
                    "persona": persona,
                    "session_id": session_id,
                    "content": full_response,
                    "timestamp": get_now().isoformat(),
                })

        async for post_event in PostProcessStep().run(ctx, config, session, turn_ctx, debug=debug):
            yield post_event.to_sse()
