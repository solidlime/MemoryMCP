"""InferenceStep: LLMストリームループとツール実行。"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from memory_mcp.application.chat.events import (
    ErrorSSE,
    TextDeltaSSE,
    ToolCallSSE,
    ToolResultSSE,
)
from memory_mcp.infrastructure.llm.base import LLMMessage
from memory_mcp.infrastructure.llm.factory import get_provider
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.chat.tools.registry import ToolRegistry
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)


class InferenceStep:
    """LLMストリームループ。TextDelta/ToolCall/ToolResult SSEを yield する。"""

    async def run(
        self,
        ctx: AppContext,
        config: ChatConfig,
        session_messages: list[LLMMessage],
        turn_ctx: ChatTurnContext,
        registry: ToolRegistry,
    ) -> AsyncIterator[TextDeltaSSE | ToolCallSSE | ToolResultSSE | ErrorSSE]:
        from memory_mcp.infrastructure.llm.base import ErrorEvent, TextDeltaEvent, ToolCallEvent

        api_key = config.get_effective_api_key()
        if not api_key:
            yield ErrorSSE(message="APIキーが設定されていません。チャット設定でAPIキーを入力してください。")
            return

        try:
            provider = get_provider(
                config.provider,
                api_key,
                config.get_effective_model(),
                config.get_effective_base_url(),
            )
        except Exception as e:
            yield ErrorSSE(message=f"LLMプロバイダーの初期化に失敗: {e}")
            return

        all_tools = registry.get_all_tools()
        messages = list(session_messages)
        messages.append(LLMMessage(role="user", content=turn_ctx.user_message))

        while turn_ctx.tool_call_count <= config.max_tool_calls:
            pending_tool_calls: list[ToolCallEvent] = []
            current_text = ""

            async for event in provider.stream(
                messages=messages,
                system=turn_ctx.system_prompt,
                tools=all_tools,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            ):
                if isinstance(event, TextDeltaEvent):
                    current_text += event.content
                    turn_ctx.full_response += event.content
                    yield TextDeltaSSE(content=event.content)
                elif isinstance(event, ToolCallEvent):
                    pending_tool_calls.append(event)
                elif isinstance(event, ErrorEvent):
                    yield ErrorSSE(message=event.message)
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
                yield ToolCallSSE(name=tc.tool_name, input=tc.tool_input, id=tc.tool_use_id)

                tool_result = await registry.execute(ctx, config, tc.tool_name, tc.tool_input)
                truncated = registry.truncate_result(tool_result, config.tool_result_max_chars)

                yield ToolResultSSE(name=tc.tool_name, result=truncated, id=tc.tool_use_id)
                turn_ctx.tool_calls_log.append({
                    "name": tc.tool_name,
                    "input": tc.tool_input,
                    "result": truncated,
                    "result_raw": tool_result,
                })
                messages.append(
                    LLMMessage(
                        role="tool",
                        content=json.dumps(truncated, ensure_ascii=False),
                        tool_call_id=tc.tool_use_id,
                    )
                )

            turn_ctx.tool_call_count += 1

        # messages (with tool calls) を turn_ctx に保存（PostStep用）
        turn_ctx.messages = messages
