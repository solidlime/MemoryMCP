"""ChatService: パイプライン型チャットオーケストレーター。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.application.chat.pipeline.context import ChatTurnContext
from memory_mcp.application.chat.pipeline.inference import InferenceStep
from memory_mcp.application.chat.pipeline.post import PostProcessStep
from memory_mcp.application.chat.pipeline.prepare import PrepareStep
from memory_mcp.application.chat.pipeline.prompt import PromptBuildStep
from memory_mcp.application.chat.session_store import SessionManager
from memory_mcp.application.chat.tools.definitions import MEMORY_TOOLS
from memory_mcp.application.chat.tools.registry import ToolRegistry
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
    ) -> AsyncIterator[str]:
        persona = ctx.persona
        db = ctx.connection.get_memory_db()
        session = _session_manager.get_or_create(persona, session_id, config.max_window_turns, db=db)

        turn_ctx = ChatTurnContext(session_id=session_id, user_message=user_message)

        # PrepareStep: pending_memory_task 待機 + EmotionDecay + コンテキスト取得
        await PrepareStep().run(ctx, session, turn_ctx, config=config)

        # PromptBuildStep: system プロンプト組み立て
        PromptBuildStep().run(ctx, config, turn_ctx)

        # InferenceStep + PostProcessStep: MCPプール共有
        async with MCPClientPool(config.mcp_servers) as mcp_pool:
            builtin = list(MEMORY_TOOLS) if config.enable_memory_tools else []
            registry = ToolRegistry(builtin, mcp_pool)

            session_messages = session.get_labeled_messages()
            async for event in InferenceStep().run(ctx, config, session_messages, turn_ctx, registry):
                yield event.to_sse()

        async for post_event in PostProcessStep().run(ctx, config, session, turn_ctx, debug=debug):
            yield post_event.to_sse()

