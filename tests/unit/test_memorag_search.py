"""Unit tests for MemoRAG search mode in SearchEngine."""

from __future__ import annotations

from unittest.mock import MagicMock

from memory_mcp.domain.search.engine import SearchEngine, SearchQuery
from memory_mcp.domain.shared.result import Success


def _make_memory(key: str):
    m = MagicMock()
    m.key = key
    m.content = f"content of {key}"
    m.emotion = None
    return m


def _make_engine(memorag_config=None, chat_config=None, memory_repo=None):
    keyword = MagicMock()
    keyword.search.return_value = Success([(_make_memory("k1"), 0.9)])
    semantic = MagicMock()
    semantic.search.return_value = Success([(_make_memory("k2"), 0.8)])
    return SearchEngine(
        keyword, semantic, None, memory_repo=memory_repo, memorag_config=memorag_config, chat_config=chat_config
    )


class TestBestSearchMode:
    def test_hybrid_when_disabled(self):
        config = MagicMock()
        config.enabled = False
        engine = _make_engine(memorag_config=config)
        assert engine.best_search_mode() == "hybrid"

    def test_smart_when_enabled_no_llm(self):
        config = MagicMock()
        config.enabled = True
        config.clue_generation_enabled = True
        chat = MagicMock()
        chat.is_configured.return_value = False
        engine = _make_engine(memorag_config=config, chat_config=chat)
        assert engine.best_search_mode() == "smart"

    def test_memorag_when_enabled_with_llm(self):
        config = MagicMock()
        config.enabled = True
        config.clue_generation_enabled = True
        chat = MagicMock()
        chat.is_configured.return_value = True
        engine = _make_engine(memorag_config=config, chat_config=chat)
        assert engine.best_search_mode() == "memorag"

    def test_smart_when_clue_disabled(self):
        config = MagicMock()
        config.enabled = True
        config.clue_generation_enabled = False
        engine = _make_engine(memorag_config=config)
        assert engine.best_search_mode() == "smart"


class TestMemoRAGSearchFallback:
    def test_falls_back_to_smart_when_no_memory_repo(self):
        config = MagicMock()
        config.enabled = True
        engine = _make_engine(memorag_config=config, memory_repo=None)
        query = SearchQuery(text="test", mode="memorag", top_k=5)
        result = engine.search(query)
        assert result.is_ok

    def test_falls_back_when_memorag_disabled(self):
        config = MagicMock()
        config.enabled = False
        repo = MagicMock()
        engine = _make_engine(memorag_config=config, memory_repo=repo)
        query = SearchQuery(text="test", mode="memorag", top_k=5)
        result = engine.search(query)
        assert result.is_ok
