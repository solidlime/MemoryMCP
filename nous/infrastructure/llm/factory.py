from __future__ import annotations

from typing import TYPE_CHECKING

from .anthropic import AnthropicProvider
from .openai_compat import OpenAICompatProvider

if TYPE_CHECKING:
    from .base import LLMProvider


_OPENAI_BASE_URL = "https://api.openai.com/v1"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_provider(provider: str, api_key: str, model: str, base_url: str = "") -> LLMProvider:
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)
    elif provider == "openai":
        return OpenAICompatProvider(api_key=api_key, model=model, base_url=base_url or _OPENAI_BASE_URL)
    elif provider == "openrouter":
        return OpenAICompatProvider(api_key=api_key, model=model, base_url=base_url or _OPENROUTER_BASE_URL)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: anthropic, openai, openrouter")
