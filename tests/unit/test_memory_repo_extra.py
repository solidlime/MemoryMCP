"""Additional unit tests for SQLiteMemoryRepository — targeting uncovered paths."""

from __future__ import annotations

import pytest

from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.shared.time_utils import get_now
from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection
from memory_mcp.infrastructure.sqlite.memory_repo import SQLiteMemoryRepository


@pytest.fixture
def sqlite_conn(tmp_path):
    conn = SQLiteConnection(data_dir=str(tmp_path), persona="test")
    conn.initialize_schema()
    yield conn
    conn.close()


@pytest.fixture
def repo(sqlite_conn):
    return SQLiteMemoryRepository(sqlite_conn)


def _make_memory(key: str = "memory_20250101120000", content: str = "test", **kwargs) -> Memory:
    now = get_now()
    return Memory(key=key, content=content, created_at=now, updated_at=now, **kwargs)


def _save_many(repo, count: int, prefix: str = "memory_202501010000") -> list[Memory]:
    memories = []
    for i in range(count):
        m = _make_memory(key=f"{prefix}{i:02d}", content=f"memory content {i}")
        repo.save(m)
        memories.append(m)
    return memories


class TestFindWithPagination:
    def test_basic_pagination(self, repo):
        _save_many(repo, 5)
        result = repo.find_with_pagination(page=1, per_page=2)
        assert result.is_ok
        memories, total = result.unwrap()
        assert total == 5
        assert len(memories) == 2

    def test_page_2(self, repo):
        _save_many(repo, 5)
        result = repo.find_with_pagination(page=2, per_page=2)
        assert result.is_ok
        memories, total = result.unwrap()
        assert total == 5
        assert len(memories) == 2

    def test_filter_by_tag(self, repo):
        m1 = _make_memory("memory_20250101000001", "tagged")
        m1.tags = ["food"]
        m2 = _make_memory("memory_20250101000002", "untagged")
        repo.save(m1)
        repo.save(m2)

        result = repo.find_with_pagination(tag="food")
        assert result.is_ok
        memories, total = result.unwrap()
        assert total == 1
        assert memories[0].content == "tagged"

    def test_filter_by_query(self, repo):
        repo.save(_make_memory("memory_20250101000001", "I love ramen"))
        repo.save(_make_memory("memory_20250101000002", "sushi is great"))

        result = repo.find_with_pagination(query="ramen")
        assert result.is_ok
        memories, total = result.unwrap()
        assert total == 1
        assert "ramen" in memories[0].content

    def test_sort_order_asc(self, repo):
        _save_many(repo, 3)
        result = repo.find_with_pagination(sort_order="asc")
        assert result.is_ok
        memories, _ = result.unwrap()
        assert len(memories) >= 1

    def test_empty_db(self, repo):
        result = repo.find_with_pagination()
        assert result.is_ok
        memories, total = result.unwrap()
        assert total == 0
        assert memories == []


class TestGetAllTags:
    def test_returns_empty_for_empty_db(self, repo):
        result = repo.get_all_tags()
        assert result.is_ok
        assert result.unwrap() == []

    def test_returns_sorted_unique_tags(self, repo):
        m1 = _make_memory("memory_20250101000001", "c1")
        m1.tags = ["b_tag", "a_tag"]
        m2 = _make_memory("memory_20250101000002", "c2")
        m2.tags = ["a_tag", "c_tag"]
        repo.save(m1)
        repo.save(m2)

        result = repo.get_all_tags()
        assert result.is_ok
        tags = result.unwrap()
        assert "a_tag" in tags
        assert "b_tag" in tags
        assert "c_tag" in tags
        assert tags == sorted(set(tags))  # sorted, unique


class TestGetByTags:
    def test_returns_memories_matching_all_tags(self, repo):
        m1 = _make_memory("memory_20250101000001", "both tags")
        m1.tags = ["food", "japanese"]
        m2 = _make_memory("memory_20250101000002", "one tag only")
        m2.tags = ["food"]
        repo.save(m1)
        repo.save(m2)

        result = repo.get_by_tags(["food", "japanese"])
        assert result.is_ok
        memories = result.unwrap()
        assert len(memories) == 1
        assert memories[0].content == "both tags"

    def test_empty_tags_returns_empty(self, repo):
        repo.save(_make_memory())
        result = repo.get_by_tags([])
        assert result.is_ok
        assert result.unwrap() == []


class TestFindSmartRecent:
    def test_returns_memories(self, repo):
        _save_many(repo, 3)
        result = repo.find_smart_recent(limit=2)
        assert result.is_ok
        assert len(result.unwrap()) == 2

    def test_empty_db(self, repo):
        result = repo.find_smart_recent()
        assert result.is_ok
        assert result.unwrap() == []


class TestSearchKeyword:
    def test_multi_word_and_logic(self, repo):
        repo.save(_make_memory("memory_20250101000001", "tokyo ramen noodles delicious"))
        repo.save(_make_memory("memory_20250101000002", "tokyo sushi fresh"))
        repo.save(_make_memory("memory_20250101000003", "osaka ramen spicy"))

        # "tokyo ramen" should match only the first record (has both "tokyo" and "ramen")
        result = repo.search_keyword("tokyo ramen")
        assert result.is_ok
        memories = result.unwrap()
        assert len(memories) == 1
        assert "tokyo ramen noodles" in memories[0][0].content

    def test_empty_query_returns_empty(self, repo):
        repo.save(_make_memory())
        result = repo.search_keyword("")
        assert result.is_ok
        assert result.unwrap() == []

    def test_limit_respected(self, repo):
        for i in range(5):
            repo.save(_make_memory(f"memory_2025010100000{i}", f"keyword match {i}"))

        result = repo.search_keyword("keyword", limit=2)
        assert result.is_ok
        assert len(result.unwrap()) == 2


class TestMemoryVersions:
    def test_save_and_get_versions(self, repo):
        m = _make_memory()
        repo.save(m)

        save_result = repo.save_version(
            memory_key=m.key,
            version=1,
            content="original content",
            metadata={"source": "test"},
            changed_by="user",
            change_type="create",
        )
        assert save_result.is_ok

        get_result = repo.get_versions(m.key)
        assert get_result.is_ok
        versions = get_result.unwrap()
        assert len(versions) == 1
        assert versions[0]["content"] == "original content"
        assert versions[0]["change_type"] == "create"

    def test_get_specific_version(self, repo):
        m = _make_memory()
        repo.save(m)
        repo.save_version(m.key, 1, "v1 content", None, "user", "create")
        repo.save_version(m.key, 2, "v2 content", None, "user", "update")

        result = repo.get_version(m.key, 1)
        assert result.is_ok
        v = result.unwrap()
        assert v is not None
        assert v["content"] == "v1 content"

    def test_get_version_not_found(self, repo):
        m = _make_memory()
        repo.save(m)

        result = repo.get_version(m.key, 99)
        assert result.is_ok
        assert result.unwrap() is None

    def test_get_latest_version_number(self, repo):
        m = _make_memory()
        repo.save(m)

        # No versions yet -> 0
        result = repo.get_latest_version_number(m.key)
        assert result.is_ok
        assert result.unwrap() == 0

        repo.save_version(m.key, 1, "v1", None, "user", "create")
        repo.save_version(m.key, 2, "v2", None, "user", "update")

        result = repo.get_latest_version_number(m.key)
        assert result.is_ok
        assert result.unwrap() == 2

    def test_get_versions_empty(self, repo):
        m = _make_memory()
        repo.save(m)
        result = repo.get_versions(m.key)
        assert result.is_ok
        assert result.unwrap() == []


class TestLogAndSearchLog:
    def test_log_search(self, repo):
        result = repo.log_search("test query", "hybrid", 5)
        assert result.is_ok

    def test_get_recent_searches(self, repo):
        repo.log_search("query 1", "hybrid", 3)
        repo.log_search("query 2", "semantic", 1)

        result = repo.get_recent_searches(limit=5)
        assert result.is_ok
        searches = result.unwrap()
        assert len(searches) == 2

    def test_get_recent_searches_limit(self, repo):
        for i in range(5):
            repo.log_search(f"query {i}", "hybrid", i)

        result = repo.get_recent_searches(limit=3)
        assert result.is_ok
        assert len(result.unwrap()) == 3


class TestCountDecayedImportant:
    def test_returns_zero_with_no_decayed(self, repo):
        m = _make_memory(importance=0.9)
        repo.save(m)
        # Default strength is 1.0, not decayed
        result = repo.count_decayed_important(min_importance=0.7, max_strength=0.3)
        assert result.is_ok
        assert result.unwrap() == 0

    def test_counts_decayed_important_memory(self, repo, sqlite_conn):
        m = _make_memory(importance=0.9)
        repo.save(m)
        # Manually set strength to a decayed value
        sqlite_conn.get_memory_db().execute("UPDATE memory_strength SET strength = 0.1 WHERE memory_key = ?", (m.key,))
        sqlite_conn.get_memory_db().commit()

        result = repo.count_decayed_important(min_importance=0.7, max_strength=0.3)
        assert result.is_ok
        assert result.unwrap() == 1


class TestGetMemoryIndex:
    def test_empty_db(self, repo):
        result = repo.get_memory_index()
        assert result.is_ok
        index = result.unwrap()
        assert index["total"] == 0
        assert index["top_tags"] == []

    def test_with_memories(self, repo):
        m1 = _make_memory("memory_20250101000001", "First", importance=0.9)
        m1.tags = ["milestone", "important"]
        m1.emotion = "joy"
        m2 = _make_memory("memory_20250101000002", "Second", importance=0.6)
        m2.tags = ["milestone"]
        m2.emotion = "neutral"
        repo.save(m1)
        repo.save(m2)

        result = repo.get_memory_index()
        assert result.is_ok
        index = result.unwrap()
        assert index["total"] == 2
        assert index["high_importance_count"] == 1
        tag_names = [t[0] for t in index["top_tags"]]
        assert "milestone" in tag_names


class TestFindRelationshipHighlights:
    def test_empty_db(self, repo):
        result = repo.find_relationship_highlights()
        assert result.is_ok
        assert result.unwrap() == []

    def test_finds_relationship_memories(self, repo):
        m = _make_memory("memory_20250101000001", "Met a special person", importance=0.9)
        m.tags = ["milestone", "important_moment"]
        repo.save(m)

        result = repo.find_relationship_highlights()
        assert result.is_ok
        memories = result.unwrap()
        assert len(memories) == 1

    def test_low_importance_excluded(self, repo):
        m = _make_memory("memory_20250101000001", "casual meeting", importance=0.3)
        m.tags = ["milestone"]
        repo.save(m)

        result = repo.find_relationship_highlights()
        assert result.is_ok
        assert len(result.unwrap()) == 0


class TestDeleteNonexistentKey:
    def test_delete_nonexistent_succeeds_silently(self, repo):
        """Deleting a non-existent key should succeed (no error)."""
        result = repo.delete("memory_key_that_does_not_exist")
        assert result.is_ok


class TestUpdatePartialFields:
    def test_update_tags_field(self, repo):
        m = _make_memory()
        repo.save(m)

        result = repo.update(m.key, tags=["new_tag", "another"])
        assert result.is_ok
        updated = result.unwrap()
        assert "new_tag" in updated.tags
        assert "another" in updated.tags

    def test_update_related_keys_field(self, repo):
        m = _make_memory()
        repo.save(m)

        result = repo.update(m.key, related_keys=["mem_other_001"])
        assert result.is_ok
        assert "mem_other_001" in result.unwrap().related_keys

    def test_update_emotion_fields(self, repo):
        m = _make_memory()
        repo.save(m)

        result = repo.update(m.key, emotion="joy", emotion_intensity=0.9)
        assert result.is_ok
        updated = result.unwrap()
        assert updated.emotion == "joy"
        assert updated.emotion_intensity == 0.9


class TestGetAllStrengths:
    def test_returns_empty_for_no_records(self, repo):
        result = repo.get_all_strengths()
        assert result.is_ok
        assert result.unwrap() == []

    def test_returns_strength_after_save(self, repo):
        m = _make_memory()
        repo.save(m)
        # strength record auto-created on save

        result = repo.get_all_strengths()
        assert result.is_ok
        strengths = result.unwrap()
        assert len(strengths) == 1
        assert strengths[0].memory_key == m.key

    def test_multiple_strengths(self, repo):
        for i in range(3):
            repo.save(_make_memory(f"memory_2025010100000{i}", f"content {i}"))

        result = repo.get_all_strengths()
        assert result.is_ok
        assert len(result.unwrap()) == 3
