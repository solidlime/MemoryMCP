"""Tests for application use case adapters."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from memory_mcp.application.use_cases import QdrantSemanticSearch, SQLiteKeywordSearch
from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.shared.result import Failure, Success
from memory_mcp.domain.shared.time_utils import get_now


def _make_memory(key="mem_001", content="test"):
    now = get_now()
    return Memory(key=key, content=content, created_at=now, updated_at=now)


class TestSQLiteKeywordSearch:
    def test_init(self):
        repo = MagicMock()
        adapter = SQLiteKeywordSearch(repo)
        assert adapter.repo is repo

    def test_search_success(self):
        memory = _make_memory()
        repo = MagicMock()
        repo.search_keyword.return_value = Success([(memory, 1.0)])

        adapter = SQLiteKeywordSearch(repo)
        result = adapter.search("test")
        assert result.is_ok
        assert len(result.value) == 1

    def test_search_failure(self):
        repo = MagicMock()
        repo.search_keyword.return_value = Failure(Exception("db error"))

        adapter = SQLiteKeywordSearch(repo)
        result = adapter.search("test")
        assert not result.is_ok

    def test_search_passes_limit(self):
        repo = MagicMock()
        repo.search_keyword.return_value = Success([])

        adapter = SQLiteKeywordSearch(repo)
        adapter.search("query", limit=5)
        repo.search_keyword.assert_called_once_with("query", 5)


class TestQdrantSemanticSearch:
    def test_init(self):
        vs = MagicMock()
        repo = MagicMock()
        adapter = QdrantSemanticSearch(vs, repo)
        assert adapter.vector_store is vs
        assert adapter.memory_repo is repo
        assert adapter._persona == ""

    def test_search_failure_propagates(self):
        vs = MagicMock()
        vs.search.return_value = Failure(Exception("qdrant error"))
        repo = MagicMock()

        adapter = QdrantSemanticSearch(vs, repo)
        result = adapter.search("query")
        assert not result.is_ok

    def test_search_success_with_memory(self):
        memory = _make_memory("mem_001")
        vs = MagicMock()
        vs.search.return_value = Success([("mem_001", 0.9)])

        repo = MagicMock()
        repo.find_by_key.return_value = Success(memory)

        adapter = QdrantSemanticSearch(vs, repo)
        adapter._persona = "test"
        result = adapter.search("query")
        assert result.is_ok
        assert len(result.value) == 1
        assert result.value[0][0] is memory
        assert result.value[0][1] == pytest.approx(0.9)

    def test_search_skips_missing_memory(self):
        vs = MagicMock()
        vs.search.return_value = Success([("mem_missing", 0.9)])

        repo = MagicMock()
        repo.find_by_key.return_value = Success(None)  # not found

        adapter = QdrantSemanticSearch(vs, repo)
        result = adapter.search("query")
        assert result.is_ok
        assert result.value == []

    def test_search_uses_persona(self):
        vs = MagicMock()
        vs.search.return_value = Success([])
        repo = MagicMock()

        adapter = QdrantSemanticSearch(vs, repo)
        adapter._persona = "my_persona"
        adapter.search("query")
        vs.search.assert_called_once_with("my_persona", "query", 10)
