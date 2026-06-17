"""CompressStep: コンテキスト圧縮。トークン予算超過時にシステムプロンプト・会話履歴を縮める。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.infrastructure.llm.token_counter import TokenCounter
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.chat.pipeline.context import ChatTurnContext
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig
    from memory_mcp.infrastructure.llm.base import LLMMessage

logger = get_logger(__name__)


class CompressStep:
    """トークン予算を超えたらシステムプロンプト・会話履歴を動的圧縮する。

    パイプライン位置: PromptBuildStep → CompressStep → InferenceStep

    圧縮段階（軽い順）:
    1. システムプロンプトの関連記憶セクションをトリム
    2. 古いツール結果を [cleared] に置換
    3. 古い会話メッセージを切り詰め

    LLMによる要約圧縮は今後の拡張。
    """

    def run(
        self,
        _ctx: AppContext,
        config: ChatConfig,
        turn_ctx: ChatTurnContext,
        session_messages: list[LLMMessage],
    ) -> list[LLMMessage]:
        """コンテキストを検査し、必要なら圧縮する。

        Returns:
            圧縮後のメッセージリスト（変更不要ならそのまま返す）
        """
        model = config.get_effective_model()
        counter = TokenCounter(model)
        total = counter.count(turn_ctx.system_prompt) + counter.count_messages(
            session_messages, ""
        )

        if config.context_max_tokens is not None:
            model_max = config.context_max_tokens
        else:
            model_max = TokenCounter.get_model_max_tokens(model)
        budget = int(model_max * config.context_compression_threshold)

        if total <= budget:
            logger.debug("CompressStep: %d/%d tokens (%.0f%%) — within budget, skip", total, budget, total * 100 / budget if budget else 0)
            return session_messages

        logger.info("CompressStep: %d/%d tokens (%.0f%%) — OVER budget, compressing...", total, budget, total * 100 / budget if budget else 0)
        before_total = total

        # Stage 1: System prompt trimming
        if getattr(config, "context_compress_system_prompt", True):
            old_len = len(turn_ctx.system_prompt)
            turn_ctx.system_prompt = self._trim_system_prompt(
                turn_ctx.system_prompt, config.context_compression_mode
            )
            logger.debug(
                "CompressStep: system prompt trimmed %d → %d chars",
                old_len, len(turn_ctx.system_prompt),
            )

        # Re-check
        total = counter.count(turn_ctx.system_prompt) + counter.count_messages(
            session_messages, ""
        )
        if total <= budget:
            return session_messages

        # Stage 2: Clear old tool results
        if getattr(config, "context_compress_history", True):
            messages = self._clear_old_tool_results(session_messages)
        else:
            messages = session_messages

        # Re-check
        total = counter.count(turn_ctx.system_prompt) + counter.count_messages(messages, "")
        if total <= budget:
            return list(messages)

        # Stage 3: Truncate old messages
        if getattr(config, "context_compress_history", True):
            keep_recent = getattr(config, "context_keep_recent_turns", 2)
            messages = self._truncate_old_messages(list(messages), keep_recent)

        total = counter.count(turn_ctx.system_prompt) + counter.count_messages(messages, "")
        logger.info("CompressStep: after compression: %d tokens", total)
        # Store compression info for SSE notification
        turn_ctx._compression_info = {
            "before_tokens": before_total,
            "after_tokens": total,
            "budget": budget,
        }
        return list(messages)

    @staticmethod
    def _trim_system_prompt(prompt: str, mode: str) -> str:
        """Trim system prompt sections by reducing memory list size.

        Sections are separated by '\\n--- ' markers.
        The 「関連記憶」 section is the primary target for trimming.
        """
        sections = prompt.split("\n--- ")
        if len(sections) <= 1:
            return prompt

        # Limits per mode (how many memory lines to keep)
        mode_limits = {
            "light": 8,       # Keep most
            "normal": 4,      # Moderate
            "aggressive": 2,  # Minimal
            "auto": 4,        # Default: normal
        }
        limit = mode_limits.get(mode, mode_limits["auto"])

        result: list[str] = [sections[0]]  # Base prompt + time (section 0)
        trimmed = False

        for sec in sections[1:]:
            if "関連記憶" in sec[:10]:
                lines = sec.split("\n")
                header = lines[0]
                memory_lines = [line for line in lines[1:] if line.strip().startswith("- ")]
                if len(memory_lines) > limit:
                    # Keep only the top-N memory lines
                    kept = memory_lines[:limit]
                    removed = len(memory_lines) - limit
                    kept.append(f"  （他 {removed} 件の関連記憶 — 必要なら memory_search で検索）")
                    result.append(f"--- {header}\n" + "\n".join(kept))
                    trimmed = True
                    continue
            elif "利用可能なSkill" in sec[:20]:
                # Truncate long skill descriptions to ~500 chars
                if len(sec) > 600:
                    result.append(f"--- {sec[:500]}...")
                    trimmed = True
                    continue
            result.append(f"--- {sec}")

        if trimmed:
            logger.debug("CompressStep: trimmed system prompt sections (mode=%s, limit=%d)", mode, limit)

        return "\n".join(result)

    @staticmethod
    def _clear_old_tool_results(messages: list[LLMMessage]) -> list[LLMMessage]:
        """Replace tool result contents older than 3 assistant turns with a compact marker.

        We keep the most recent 3 assistant turns' tool results intact.
        Tool results before that are replaced with '[cleared]'.
        """
        from memory_mcp.infrastructure.llm.base import LLMMessage

        # Find indices of assistant messages
        assistant_indices = [i for i, m in enumerate(messages) if m.role == "assistant"]

        if len(assistant_indices) <= 3:
            return messages  # Not enough history

        # Tool results before the 4th-to-last assistant message are fair game
        cutoff = assistant_indices[-4]  # Messages before this are old

        cleared_count = 0
        result: list[LLMMessage] = []
        for i, msg in enumerate(messages):
            if msg.role == "tool" and i < cutoff:
                result.append(
                    LLMMessage(
                        role="tool",
                        content="[previous tool output cleared]",
                        tool_call_id=msg.tool_call_id,
                    )
                )
                cleared_count += 1
            else:
                result.append(msg)

        if cleared_count:
            logger.debug("CompressStep: cleared %d old tool results", cleared_count)

        return result

    @staticmethod
    def _truncate_old_messages(messages: list[LLMMessage], keep_recent_turns: int) -> list[LLMMessage]:
        """Truncate older user/assistant messages to 300 chars.

        Keeps the most recent N turns intact; truncates everything before that.
        Tool messages are left as-is (handled by _clear_old_tool_results).
        """
        from memory_mcp.infrastructure.llm.base import LLMMessage

        keep_count = keep_recent_turns * 2  # user + assistant = one turn
        if len(messages) <= keep_count:
            return messages

        result: list[LLMMessage] = []
        truncated_count = 0

        for i, msg in enumerate(messages):
            if i < len(messages) - keep_count and msg.role in ("user", "assistant"):
                content = msg.content or ""
                if len(content) > 300:
                    result.append(
                        LLMMessage(
                            role=msg.role,
                            content=f"[旧]{content[:300]}...",
                            timestamp=msg.timestamp,
                            time_label=msg.time_label or "(旧)",
                            tool_call_id=msg.tool_call_id,
                            tool_calls=msg.tool_calls,
                            content_parts=msg.content_parts,
                        )
                    )
                    truncated_count += 1
                else:
                    result.append(msg)
            else:
                result.append(msg)

        if truncated_count:
            logger.debug(
                "CompressStep: truncated %d old messages (kept %d recent turns)",
                truncated_count, keep_recent_turns,
            )

        return result
