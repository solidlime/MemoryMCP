from __future__ import annotations

from pydantic import BaseModel
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
    forgetting: ForgettingConfig = ForgettingConfig()
    timezone: str = "Asia/Tokyo"
    data_dir: str = "./data"
    import_dir: str = ""  # empty = auto-import disabled
    log_level: str = "INFO"
    default_persona: str = "default"
    contradiction_threshold: float = 0.85
    duplicate_threshold: float = 0.90


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
