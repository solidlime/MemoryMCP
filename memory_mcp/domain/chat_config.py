from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, field_validator

from memory_mcp.domain.shared.time_utils import format_iso, get_now

if TYPE_CHECKING:
    import sqlite3

# Environment variable names for API keys per provider
_ENV_API_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

# Default model names per provider
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-opus-4-5",
    "openai": "gpt-4o",
    "openrouter": "openai/gpt-4o",
}

# Default base URLs per provider (empty means use SDK default)
_DEFAULT_BASE_URLS: dict[str, str] = {
    "anthropic": "",
    "openai": "",
    "openrouter": "https://openrouter.ai/api/v1",
}


class ChatConfig(BaseModel):
    persona: str = "default"
    provider: str = "anthropic"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    max_window_turns: int = 3
    max_tool_calls: int = 5
    auto_extract: bool = True
    extract_model: str = ""
    extract_max_tokens: int = 512
    tool_result_max_chars: int = 4000
    mcp_servers: list[dict] = []
    enabled_skills: list[str] = []
    enable_memory_tools: bool = True
    # Generative Agents-style reflection
    reflection_enabled: bool = True
    reflection_threshold: float = 3.0  # sum of importance scores to trigger reflection
    reflection_min_interval_hours: float = 1.0
    # Session summarization
    session_summarize: bool = True
    # Retrieval composite scoring weights
    retrieval_recency_weight: float = 0.3
    retrieval_importance_weight: float = 0.3
    retrieval_relevance_weight: float = 0.4
    updated_at: str | None = None

    @field_validator("temperature")
    @classmethod
    def _clamp_temperature(cls, v: float) -> float:
        return max(0.0, min(2.0, v))

    @field_validator("max_tokens")
    @classmethod
    def _clamp_max_tokens(cls, v: int) -> int:
        return max(1, min(32768, v))

    @field_validator("max_window_turns")
    @classmethod
    def _clamp_window_turns(cls, v: int) -> int:
        return max(1, min(50, v))

    @field_validator("max_tool_calls")
    @classmethod
    def _clamp_tool_calls(cls, v: int) -> int:
        return max(0, min(20, v))

    @field_validator("extract_max_tokens")
    @classmethod
    def _clamp_extract_max_tokens(cls, v: int) -> int:
        return max(64, min(2048, v))

    @field_validator("tool_result_max_chars")
    @classmethod
    def _clamp_tool_result_max_chars(cls, v: int) -> int:
        return max(500, min(100000, v))

    @field_validator("reflection_threshold")
    @classmethod
    def _clamp_reflection_threshold(cls, v: float) -> float:
        return max(0.1, min(100.0, v))

    @field_validator("reflection_min_interval_hours")
    @classmethod
    def _clamp_reflection_interval(cls, v: float) -> float:
        return max(0.0, min(168.0, v))

    @field_validator("retrieval_recency_weight", "retrieval_importance_weight", "retrieval_relevance_weight")
    @classmethod
    def _clamp_retrieval_weights(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    def get_effective_api_key(self) -> str:
        """Return stored API key or fall back to environment variable."""
        if self.api_key:
            return self.api_key
        env_var = _ENV_API_KEYS.get(self.provider, "")
        return os.environ.get(env_var, "")

    def get_effective_model(self) -> str:
        """Return stored model name or default for the provider."""
        if self.model:
            return self.model
        return _DEFAULT_MODELS.get(self.provider, "")

    def get_effective_base_url(self) -> str:
        """Return stored base URL or provider default."""
        if self.base_url:
            return self.base_url
        return _DEFAULT_BASE_URLS.get(self.provider, "")

    def is_configured(self) -> bool:
        """Return True if provider has an API key available."""
        return bool(self.get_effective_api_key())

    def to_safe_dict(self) -> dict:
        """Return config as dict with API key masked."""
        d = self.model_dump()
        raw_key = d.get("api_key", "")
        if raw_key:
            visible = raw_key[:4] if len(raw_key) > 4 else ""
            d["api_key"] = visible + "****"
        d["is_configured"] = self.is_configured()
        d["effective_model"] = self.get_effective_model()
        d["effective_base_url"] = self.get_effective_base_url()
        return d


class ChatConfigRepository:
    """SQLite CRUD for ChatConfig, stored in the persona's memory.sqlite."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get(self, persona: str) -> ChatConfig:
        """Load config for persona, returning defaults if not found."""
        row = self._db.execute(
            "SELECT persona, provider, model, api_key, base_url, system_prompt, "
            "temperature, max_tokens, max_window_turns, max_tool_calls, updated_at, "
            "auto_extract, extract_model, extract_max_tokens, "
            "tool_result_max_chars, mcp_servers, enabled_skills, "
            "reflection_enabled, reflection_threshold, reflection_min_interval_hours, "
            "session_summarize, "
            "retrieval_recency_weight, retrieval_importance_weight, retrieval_relevance_weight "
            "FROM chat_settings WHERE persona = ?",
            (persona,),
        ).fetchone()
        if row is None:
            return ChatConfig(persona=persona)
        return ChatConfig(
            persona=row[0],
            provider=row[1] or "anthropic",
            model=row[2] or "",
            api_key=row[3] or "",
            base_url=row[4] or "",
            system_prompt=row[5] or "",
            temperature=float(row[6]) if row[6] is not None else 0.7,
            max_tokens=int(row[7]) if row[7] is not None else 2048,
            max_window_turns=int(row[8]) if row[8] is not None else 3,
            max_tool_calls=int(row[9]) if row[9] is not None else 5,
            updated_at=row[10],
            auto_extract=bool(row[11]) if row[11] is not None else True,
            extract_model=row[12] or "",
            extract_max_tokens=int(row[13]) if row[13] is not None else 512,
            tool_result_max_chars=int(row[14]) if row[14] is not None else 4000,
            mcp_servers=json.loads(row[15] or "[]"),
            enabled_skills=json.loads(row[16] or "[]"),
            reflection_enabled=bool(row[17]) if row[17] is not None else True,
            reflection_threshold=float(row[18]) if row[18] is not None else 3.0,
            reflection_min_interval_hours=float(row[19]) if row[19] is not None else 1.0,
            session_summarize=bool(row[20]) if row[20] is not None else True,
            retrieval_recency_weight=float(row[21]) if row[21] is not None else 0.3,
            retrieval_importance_weight=float(row[22]) if row[22] is not None else 0.3,
            retrieval_relevance_weight=float(row[23]) if row[23] is not None else 0.4,
        )

    def save(self, config: ChatConfig) -> None:
        """Insert or replace config for persona."""
        now = format_iso(get_now())
        self._db.execute(
            """
            INSERT INTO chat_settings
                (persona, provider, model, api_key, base_url, system_prompt,
                 temperature, max_tokens, max_window_turns, max_tool_calls,
                 auto_extract, extract_model, extract_max_tokens,
                 tool_result_max_chars, mcp_servers, enabled_skills,
                 reflection_enabled, reflection_threshold, reflection_min_interval_hours,
                 session_summarize,
                 retrieval_recency_weight, retrieval_importance_weight, retrieval_relevance_weight,
                 updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(persona) DO UPDATE SET
                provider=excluded.provider,
                model=excluded.model,
                api_key=excluded.api_key,
                base_url=excluded.base_url,
                system_prompt=excluded.system_prompt,
                temperature=excluded.temperature,
                max_tokens=excluded.max_tokens,
                max_window_turns=excluded.max_window_turns,
                max_tool_calls=excluded.max_tool_calls,
                auto_extract=excluded.auto_extract,
                extract_model=excluded.extract_model,
                extract_max_tokens=excluded.extract_max_tokens,
                tool_result_max_chars=excluded.tool_result_max_chars,
                mcp_servers=excluded.mcp_servers,
                enabled_skills=excluded.enabled_skills,
                reflection_enabled=excluded.reflection_enabled,
                reflection_threshold=excluded.reflection_threshold,
                reflection_min_interval_hours=excluded.reflection_min_interval_hours,
                session_summarize=excluded.session_summarize,
                retrieval_recency_weight=excluded.retrieval_recency_weight,
                retrieval_importance_weight=excluded.retrieval_importance_weight,
                retrieval_relevance_weight=excluded.retrieval_relevance_weight,
                updated_at=excluded.updated_at
            """,
            (
                config.persona,
                config.provider,
                config.model,
                config.api_key,
                config.base_url,
                config.system_prompt,
                config.temperature,
                config.max_tokens,
                config.max_window_turns,
                config.max_tool_calls,
                int(config.auto_extract),
                config.extract_model,
                config.extract_max_tokens,
                config.tool_result_max_chars,
                json.dumps(config.mcp_servers, ensure_ascii=False),
                json.dumps(config.enabled_skills, ensure_ascii=False),
                int(config.reflection_enabled),
                config.reflection_threshold,
                config.reflection_min_interval_hours,
                int(config.session_summarize),
                config.retrieval_recency_weight,
                config.retrieval_importance_weight,
                config.retrieval_relevance_weight,
                now,
            ),
        )
        self._db.commit()

    def delete(self, persona: str) -> None:
        self._db.execute("DELETE FROM chat_settings WHERE persona = ?", (persona,))
        self._db.commit()
