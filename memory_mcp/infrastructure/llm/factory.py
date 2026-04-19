from __future__ import annotations

from typing import TYPE_CHECKING

from .anthropic import AnthropicProvider
from .openai_compat import OpenAICompatProvider

if TYPE_CHECKING:
    from .base import LLMProvider


def get_provider(provider: str, api_key: str, model: str, base_url: str = "") -> LLMProvider:
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)
    elif provider in ("openai", "openrouter"):
        return OpenAICompatProvider(api_key=api_key, model=model, base_url=base_url or None)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: anthropic, openai, openrouter")
