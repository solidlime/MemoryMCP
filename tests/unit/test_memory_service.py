"""Tests for MemoryService with an InMemory repository."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from memory_mcp.domain.memory.service import MemoryService
from memory_mcp.domain.shared.errors import RepositoryError
from memory_mcp.domain.shared.result import Failure, Result, Success

if TYPE_CHECKING:
    from memory_mcp.domain.memory.entities import Memory, MemoryStrength

TZ = ZoneInfo("Asia/Tokyo")


# ---------------------------------------------------------------------------
# InMemory implementations for testing
# ---------------------------------------------------------------------------

class InMemoryMemoryRepository:
    """Protocol-compatible in-memory repo for MemoryService tests."""

    def __init__(self) -> None:
        self._store: dict[str, Memory] = {}
        self._strengths: dict[str, MemoryStrength] = {}
        self._blocks: dict[str, dict] = {}

    def save(self, memory: Memory) -> Result[str, RepositoryError]:
        self._store[memory.key] = memory
        return Success(memory.key)

    def find_by_key(self, key: str) -> Result[Memory | None, RepositoryError]:
        return Success(self._store.get(key))

    def find_recent(self, limit: int = 10) -> Result[list[Memory], RepositoryError]:
        memories = sorted(
            self._store.values(), key=lambda m: m.updated_at, reverse=True
        )
        return Success(memories[:limit])

    def find_by_tags(
        self, tags: list[str], limit: int = 10
    ) -> Result[list[Memory], RepositoryError]:
        tag_set = set(tags)
        result = [m for m in self._store.values() if set(m.tags) & tag_set]
        return Success(result[:limit])

    def update(self, key: str, **kwargs: Any) -> Result[Memory, RepositoryError]:
        if key not in self._store:
            return Failure(RepositoryError(f"Not found: {key}"))
        m = self._store[key]
        for field, value in kwargs.items():
            if hasattr(m, field):
                setattr(m, field, value)
        self._store[key] = m
        return Success(m)

    def delete(self, key: str) -> Result[None, RepositoryError]:
        self._store.pop(key, None)
        return Success(None)

    def count(self) -> Result[int, RepositoryError]:
        return Success(len(self._store))

    def search_keyword(
        self, query: str, limit: int = 10
    ) -> Result[list[tuple[Memory, float]], RepositoryError]:
        results = []
        for m in self._store.values():
            if query.lower() in m.content.lower():
                results.append((m, 1.0))
        return Success(results[:limit])

    def find_all(self) -> Result[list[Memory], RepositoryError]:
        return Success(list(self._store.values()))

    def get_strength(
        self, key: str
    ) -> Result[MemoryStrength | None, RepositoryError]:
        return Success(self._strengths.get(key))

    def save_strength(
        self, strength: MemoryStrength
    ) -> Result[None, RepositoryError]:
        self._strengths[strength.memory_key] = strength
        return Success(None)

    def get_all_strengths(
        self,
    ) -> Result[list[MemoryStrength], RepositoryError]:
        return Success(list(self._strengths.values()))

    def get_block(
        self, block_name: str
    ) -> Result[dict | None, RepositoryError]:
        return Success(self._blocks.get(block_name))

    def save_block(
        self,
        block_name: str,
        content: str,
        block_type: str = "custom",
        max_tokens: int = 500,
        priority: int = 0,
        metadata: dict | None = None,
    ) -> Result[None, RepositoryError]:
        self._blocks[block_name] = {
            "block_name": block_name,
            "content": content,
            "block_type": block_type,
            "max_tokens": max_tokens,
            "priority": priority,
            "metadata": metadata or {},
        }
        return Success(None)

    def list_blocks(self) -> Result[list[dict], RepositoryError]:
        return Success(list(self._blocks.values()))

    def delete_block(self, block_name: str) -> Result[None, RepositoryError]:
        self._blocks.pop(block_name, None)
        return Success(None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo():
    return InMemoryMemoryRepository()


@pytest.fixture
def service(repo):
    return MemoryService(repo)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateMemory:
    def test_create_success(self, service: MemoryService):
        result = service.create_memory(content="Hello world", importance=0.7)
        assert result.is_ok
        memory = result.unwrap()
        assert memory.content == "Hello world"
        assert memory.importance == 0.7

    def test_create_strips_whitespace(self, service: MemoryService):
        result = service.create_memory(content="  spaced  ")
        assert result.is_ok
        assert result.unwrap().content == "spaced"

    def test_create_empty_content_fails(self, service: MemoryService):
        result = service.create_memory(content="")
        assert not result.is_ok

    def test_create_whitespace_only_fails(self, service: MemoryService):
        result = service.create_memory(content="   ")
        assert not result.is_ok

    def test_create_with_tags(self, service: MemoryService):
        result = service.create_memory(content="tagged", tags=["a", "b"])
        assert result.is_ok
        assert result.unwrap().tags == ["a", "b"]

    def test_importance_clamped(self, service: MemoryService):
        r = service.create_memory(content="high", importance=2.0)
        assert r.is_ok
        assert r.unwrap().importance == 1.0


class TestGetMemory:
    def test_get_existing(self, service: MemoryService):
        created = service.create_memory(content="find me").unwrap()
        result = service.get_memory(created.key)
        assert result.is_ok
        assert result.unwrap().content == "find me"

    def test_get_nonexistent(self, service: MemoryService):
        result = service.get_memory("memory_99999999999999")
        assert not result.is_ok


class TestUpdateMemory:
    def test_update_content(self, service: MemoryService):
        created = service.create_memory(content="original").unwrap()
        result = service.update_memory(created.key, content="modified")
        assert result.is_ok
        assert result.unwrap().content == "modified"

    def test_update_nonexistent(self, service: MemoryService):
        result = service.update_memory("memory_99999999999999", content="x")
        assert not result.is_ok


class TestDeleteMemory:
    def test_delete_existing(self, service: MemoryService):
        created = service.create_memory(content="remove me").unwrap()
        result = service.delete_memory(created.key)
        assert result.is_ok
        # Verify it's gone
        get_result = service.get_memory(created.key)
        assert not get_result.is_ok

    def test_delete_nonexistent(self, service: MemoryService):
        result = service.delete_memory("memory_99999999999999")
        assert not result.is_ok


class TestGetRecent:
    def test_returns_most_recent(self, service: MemoryService):
        keys = []
        for i in range(5):
            with patch(
                "memory_mcp.domain.memory.service.generate_memory_key",
                return_value=f"memory_2025010100000{i}",
            ):
                r = service.create_memory(content=f"memory {i}")
                assert r.is_ok
                keys.append(r.unwrap().key)
        result = service.get_recent(limit=3)
        assert result.is_ok
        assert len(result.unwrap()) == 3

    def test_empty_repo(self, service: MemoryService):
        result = service.get_recent()
        assert result.is_ok
        assert result.unwrap() == []


class TestGetStats:
    def test_stats_empty(self, service: MemoryService):
        result = service.get_stats()
        assert result.is_ok
        stats = result.unwrap()
        assert stats["total_count"] == 0
        assert stats["tag_distribution"] == {}

    def test_stats_with_data(self, service: MemoryService):
        with patch(
            "memory_mcp.domain.memory.service.generate_memory_key",
            return_value="memory_20250101000001",
        ):
            service.create_memory(content="a", tags=["food"], emotion="joy")
        with patch(
            "memory_mcp.domain.memory.service.generate_memory_key",
            return_value="memory_20250101000002",
        ):
            service.create_memory(content="b", tags=["food", "travel"], emotion="sadness")
        result = service.get_stats()
        assert result.is_ok
        stats = result.unwrap()
        assert stats["total_count"] == 2
        assert stats["tag_distribution"]["food"] == 2
        assert stats["tag_distribution"]["travel"] == 1
        assert stats["emotion_distribution"]["joy"] == 1
        assert stats["emotion_distribution"]["sadness"] == 1


class TestBoostRecall:
    def test_boost_creates_strength_if_missing(self, service: MemoryService):
        created = service.create_memory(content="remember").unwrap()
        result = service.boost_recall(created.key)
        assert result.is_ok
        strength = result.unwrap()
        assert strength.recall_count == 1
        assert strength.stability == 1.5

    def test_boost_increments(self, service: MemoryService, repo: InMemoryMemoryRepository):
        created = service.create_memory(content="recall").unwrap()
        service.boost_recall(created.key)
        result = service.boost_recall(created.key)
        assert result.is_ok
        assert result.unwrap().recall_count == 2


class TestMemoryBlocks:
    def test_write_and_read_block(self, service: MemoryService):
        wr = service.write_block("test_block", "block content")
        assert wr.is_ok
        rd = service.read_block("test_block")
        assert rd.is_ok
        assert rd.unwrap()["content"] == "block content"

    def test_list_blocks(self, service: MemoryService):
        service.write_block("b1", "c1")
        service.write_block("b2", "c2")
        result = service.list_blocks()
        assert result.is_ok
        assert len(result.unwrap()) == 2

    def test_delete_block(self, service: MemoryService):
        service.write_block("del_block", "content")
        service.delete_block("del_block")
        result = service.read_block("del_block")
        assert result.is_ok
        assert result.unwrap() is None

    def test_write_empty_name_fails(self, service: MemoryService):
        result = service.write_block("", "content")
        assert not result.is_ok

    def test_write_empty_content_fails(self, service: MemoryService):
        result = service.write_block("name", "")
        assert not result.is_ok
