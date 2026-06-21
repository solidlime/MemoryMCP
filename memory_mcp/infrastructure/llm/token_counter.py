"""Token counting with tiktoken priority and heuristic fallback."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Default model max context windows (tokens)
MODEL_MAX_CONTEXT: dict[str, int] = {
    "claude": 200_000,
    "claude-3": 200_000,
    "claude-3.5": 200_000,
    "claude-3.7": 200_000,
    "claude-4": 200_000,
    "claude-opus": 200_000,
    "claude-sonnet": 200_000,
    "claude-haiku": 200_000,
    "gpt-4o": 128_000,
    "gpt-4": 8_192,
    "gpt-4-turbo": 128_000,
    "gpt-3.5-turbo": 16_384,
    "o1": 200_000,
    "o3": 200_000,
    "gemini": 1_000_000,
    "llama": 128_000,
    "mistral": 128_000,
    "deepseek": 128_000,
}


class TokenCounter:
    """Count tokens in text and messages. Uses tiktoken if available, else heuristic."""

    _DEFAULT_MODEL_FOR_ENCODING = "gpt-4o"

    def __init__(self, model: str = "") -> None:
        self._model = model
        self._encoder = None
        self._has_tiktoken = False
        try:
            import tiktoken  # noqa: PLC0415

            encoding_name = self._resolve_encoding(model)
            self._encoder = tiktoken.encoding_for_model(encoding_name)
            self._has_tiktoken = True
            logger.debug("TokenCounter: using tiktoken encoder for %s", encoding_name)
        except Exception:
            logger.debug("TokenCounter: tiktoken not available, using heuristic")
            self._has_tiktoken = False

    @staticmethod
    def _resolve_encoding(model: str) -> str:
        """Map model name to tiktoken encoding name."""
        model_lower = model.lower()
        # Claude models use cl100k_base (best approximation)
        if any(m in model_lower for m in ("claude",)):
            return "gpt-4o"
        if "gpt-4" in model_lower:
            return "gpt-4o"
        if "gpt-3.5" in model_lower:
            return "gpt-3.5-turbo"
        if "o1" in model_lower or "o3" in model_lower:
            return "o1"
        return "gpt-4o"  # default fallback

    def count(self, text: str) -> int:
        """Count tokens in a text string."""
        if not text:
            return 0
        if self._has_tiktoken and self._encoder:
            try:
                return len(self._encoder.encode(text))
            except Exception as e:
                logger.debug("tiktoken encode failed, falling back to heuristic: %s", e)
        return self._heuristic_count(text)

    def count_messages(self, messages: list, system_prompt: str = "") -> int:
        """Count tokens across messages + system_prompt.

        Args:
            messages: List of LLMMessage objects with 'content' attribute
            system_prompt: System prompt string

        Returns:
            Total estimated token count
        """
        total = self.count(system_prompt)
        for msg in messages:
            content = getattr(msg, "content", "") or ""
            total += self.count(content)
            # Count tool_calls overhead
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                total += self.count(str(tc.get("name", "")))
                total += self.count(str(tc.get("input", "")))
        return total

    @staticmethod
    def _heuristic_count(text: str) -> int:
        """Simple heuristic: Japanese ~1 char/token, English ~4 chars/token.

        This is a conservative estimate that slightly overcounts for safety.
        """
        if not text:
            return 0
        # Count CJK characters (1 char ≈ 1 token)
        cjk_count = 0
        ascii_count = 0
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or "\u3400" <= ch <= "\u4dbf":
                cjk_count += 1
            else:
                ascii_count += 1
        # CJK: 1-to-1, ASCII: 4 chars per token
        return cjk_count + max(1, ascii_count // 4)

    @staticmethod
    def get_model_max_tokens(model: str) -> int:
        """Get the context window size for a model name.

        Args:
            model: Model name string (e.g., 'claude-opus-4-5', 'gpt-4o', 'openai/gpt-4o')

        Returns:
            Max tokens for the model, defaulting to 128000 for unknown models.
        """
        model_lower = model.lower()
        # Strip provider prefix for OpenRouter (e.g., 'openai/gpt-4o' → 'gpt-4o')
        if "/" in model_lower:
            model_lower = model_lower.split("/", 1)[1]

        for key, max_tokens in sorted(MODEL_MAX_CONTEXT.items(), key=lambda x: -len(x[0])):
            if key in model_lower:
                return max_tokens
        return 128_000  # conservative default
