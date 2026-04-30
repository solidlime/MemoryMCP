"""SessionSummarizer: 会話ターンを記憶に圧縮して保存する。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.infrastructure.llm.base import LLMMessage
from memory_mcp.infrastructure.llm.factory import get_provider
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig

logger = get_logger(__name__)

_SUMMARIZE_PROMPT = """\
以下の会話を2〜3文の日本語で簡潔に要約してください。
重要な情報・決定事項・感情的な出来事を優先してください。

【会話】
{conversation}

【出力】
要約文のみ。JSON不要。
"""


async def summarize_and_store(
    ctx: AppContext,
    config: ChatConfig,
    turns: list[dict],
) -> str | None:
    """古い会話ターンをLLMで要約して記憶に保存する。

    Args:
        ctx: AppContext
        config: ChatConfig
        turns: {"role": str, "content": str} の辞書リスト

    Returns:
        生成された要約文字列。スキップ時またはエラー時はNone。
    """
    if not getattr(config, "session_summarize", True):
        return None

    if not turns:
        return None

    api_key = config.get_effective_api_key()
    model = config.extract_model.strip() or config.get_effective_model()
    if not api_key or not model:
        return None

    conversation_lines = []
    for turn in turns:
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        if role == "user":
            conversation_lines.append(f"User: {content[:300]}")
        elif role == "assistant":
            conversation_lines.append(f"Assistant: {content[:300]}")

    if not conversation_lines:
        return None

    prompt = _SUMMARIZE_PROMPT.format(conversation="\n".join(conversation_lines))

    try:
        provider = get_provider(
            config.provider, api_key, model, config.get_effective_base_url()
        )
    except Exception as e:
        logger.warning("SessionSummarizer: provider init failed: %s", e)
        return None

    from memory_mcp.infrastructure.llm.base import DoneEvent, ErrorEvent, TextDeltaEvent

    text = ""
    try:
        async for event in provider.stream(
            messages=[LLMMessage(role="user", content=prompt)],
            system="",
            tools=[],
            temperature=0.0,
            max_tokens=256,
        ):
            if isinstance(event, TextDeltaEvent):
                text += event.content
            elif isinstance(event, (DoneEvent, ErrorEvent)):
                break
    except Exception as e:
        logger.warning("SessionSummarizer: LLM call failed: %s", e)
        return None

    summary = text.strip()
    if not summary:
        return None

    ctx.memory_service.create_memory(
        content=summary,
        importance=0.65,
        tags=["session_summary"],
        emotion="neutral",
    )
    logger.debug("SessionSummarizer: stored summary for persona=%s (%d chars)", ctx.persona, len(summary))
    return summary
