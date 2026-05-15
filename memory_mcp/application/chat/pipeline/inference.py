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
                turn_ctx.tool_calls_log.append(
                    {
                        "name": tc.tool_name,
                        "input": tc.tool_input,
                        "result": truncated,
                        "result_raw": tool_result,
                    }
                )
                messages.append(
                    LLMMessage(
                        role="tool",
                        content=json.dumps(truncated, ensure_ascii=False),
                        tool_call_id=tc.tool_use_id,
                    )
                )

            turn_ctx.tool_call_count += 1

            # Inject image data as user message content_parts
            # (OpenAI API requires image_url parts in user messages, not tool messages)
            image_parts: list[dict] = []
            logger.debug(
                "InferenceStep: checking %d tool call results for image data",
                len(pending_tool_calls),
            )
            for log_entry in turn_ctx.tool_calls_log[-len(pending_tool_calls):]:
                result = log_entry.get("result_raw", log_entry.get("result", {}))
                if isinstance(result, dict):
                    ct = result.get("content_type", "image/png")
                    if result.get("content_base64"):
                        logger.info("InferenceStep: found content_base64 in tool result (len=%d)", len(result['content_base64']))
                        image_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{ct};base64,{result['content_base64']}", "detail": "auto"},
                        })
                    if result.get("artifacts"):
                        logger.info("InferenceStep: found %d artifacts in tool result", len(result['artifacts']))
                        for b64 in result["artifacts"]:
                            if isinstance(b64, str) and len(b64) > 100:
                                image_parts.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "auto"},
                                })

            if image_parts:
                logger.info(
                    "InferenceStep: injecting %d image content_parts into user message (types: %s)",
                    len(image_parts),
                    [p.get("type", "?") for p in image_parts],
                )
                messages.append(LLMMessage(
                    role="user",
                    content="The tool execution produced image(s). Please analyze:",
                    content_parts=[
                        {"type": "text", "text": "The previous tool execution produced the following image(s). Please analyze them carefully."},
                        *image_parts
                    ],
                ))
            else:
                logger.debug(
                    "InferenceStep: no image data found in %d tool calls",
                    len(pending_tool_calls),
                )

        # messages (with tool calls) を turn_ctx に保存（PostStep用）
        turn_ctx.messages = messages
