from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""

    model: str = "cl-nagoya/ruri-v3-30m"
    device: str = "cpu"
    batch_size: int = 32


class RerankerConfig(BaseModel):
    """Reranker model configuration."""

    model: str = "hotchpotch/japanese-reranker-xsmall-v2"
    enabled: bool = True


class QdrantConfig(BaseModel):
    """Qdrant vector store configuration."""

    url: str = "http://localhost:6333"
    api_key: str | None = None
    collection_prefix: str = "memory_"


class ServerConfig(BaseModel):
    """HTTP/MCP server configuration."""

    host: str = "0.0.0.0"
    port: int = 26262


class SummarizationConfig(BaseModel):
    """LLM-based summarization configuration."""

    enabled: bool = False
    use_llm: bool = False
    llm_api_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str | None = None
    llm_model: str = "anthropic/claude-3.5-sonnet"
    llm_max_tokens: int = 500
    check_interval_seconds: int = 3600
    min_importance: float = 0.3


class ForgettingConfig(BaseModel):
    """Ebbinghaus forgetting curve configuration."""

    enabled: bool = True
    decay_interval_seconds: int = 3600
    min_strength: float = 0.01


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_MCP_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    server: ServerConfig = ServerConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    reranker: RerankerConfig = RerankerConfig()
    qdrant: QdrantConfig = QdrantConfig()
    summarization: SummarizationConfig = SummarizationConfig()
    forgetting: ForgettingConfig = ForgettingConfig()
    timezone: str = "Asia/Tokyo"
    data_root: str = "./data"
    log_level: str = "INFO"
    default_persona: str = "default"
    contradiction_threshold: float = 0.85
    duplicate_threshold: float = 0.90

    @computed_field
    @property
    def data_dir(self) -> str:
        """Persona別DB格納ディレクトリ: {data_root}/memory"""
        return f"{self.data_root}/memory"

    @computed_field
    @property
    def import_dir(self) -> str:
        """Auto-Import ZIP配置ディレクトリ: {data_root}/import"""
        return f"{self.data_root}/import"

    @computed_field
    @property
    def cache_dir(self) -> str:
        """モデルキャッシュディレクトリ: {data_root}/cache"""
        return f"{self.data_root}/cache"

    @computed_field
    @property
    def config_dir(self) -> str:
        """設定ファイルディレクトリ: {data_root}/config"""
        return f"{self.data_root}/config"

    def ensure_directories(self) -> None:
        """起動時に必要なディレクトリを全て作成する。"""
        dirs = [
            self.data_dir,
            self.import_dir,
            Path(self.import_dir) / "done",
            self.cache_dir,
            Path(self.cache_dir) / "huggingface",
            Path(self.cache_dir) / "sentence_transformers",
            Path(self.cache_dir) / "torch",
            self.config_dir,
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
