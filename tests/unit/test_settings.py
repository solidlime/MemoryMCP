"""Tests for Settings configuration."""

from __future__ import annotations

from memory_mcp.config.settings import (
    EmbeddingConfig,
    ForgettingConfig,
    QdrantConfig,
    RerankerConfig,
    ServerConfig,
    Settings,
)


class TestDefaultValues:
    def test_server_defaults(self):
        cfg = ServerConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 26262

    def test_embedding_defaults(self):
        cfg = EmbeddingConfig()
        assert cfg.model == "cl-nagoya/ruri-v3-30m"
        assert cfg.device == "cpu"
        assert cfg.batch_size == 32

    def test_reranker_defaults(self):
        cfg = RerankerConfig()
        assert cfg.model == "hotchpotch/japanese-reranker-xsmall-v2"
        assert cfg.enabled is True

    def test_qdrant_defaults(self):
        cfg = QdrantConfig()
        assert cfg.url == "http://localhost:6333"
        assert cfg.api_key is None
        assert cfg.collection_prefix == "memory_"

    def test_forgetting_defaults(self):
        cfg = ForgettingConfig()
        assert cfg.enabled is True
        assert cfg.decay_interval_seconds == 3600
        assert cfg.min_strength == 0.01


class TestSettings:
    def test_full_defaults(self, monkeypatch):
        # CI環境で MEMORY_MCP_DATA_DIR が設定されている可能性があるため削除
        monkeypatch.delenv("MEMORY_MCP_DATA_DIR", raising=False)
        s = Settings()
        assert s.timezone == "Asia/Tokyo"
        assert s.data_dir == "./data"
        assert s.log_level == "INFO"
        assert s.default_persona == "default"
        assert s.server.port == 26262
        assert s.contradiction_threshold == 0.85
        assert s.duplicate_threshold == 0.90

    def test_env_override_simple(self, monkeypatch):
        monkeypatch.setenv("MEMORY_MCP_TIMEZONE", "UTC")
        monkeypatch.setenv("MEMORY_MCP_LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.timezone == "UTC"
        assert s.log_level == "DEBUG"

    def test_env_override_nested(self, monkeypatch):
        monkeypatch.setenv("MEMORY_MCP_SERVER__PORT", "9999")
        s = Settings()
        assert s.server.port == 9999

    def test_env_override_data_dir(self, monkeypatch):
        monkeypatch.setenv("MEMORY_MCP_DATA_DIR", "/custom/data")
        s = Settings()
        assert s.data_dir == "/custom/data"
