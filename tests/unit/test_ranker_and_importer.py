"""Unit tests for TopicAffinityRanker and convo_importer."""

from __future__ import annotations

import json
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.search.engine import SearchQuery, SearchResult
from memory_mcp.domain.search.ranker import TopicAffinityRanker
from memory_mcp.migration.importers.convo_importer import parse_conversation_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(key: str, tags: list[str], score: float = 0.5) -> SearchResult:
    now = datetime.now(UTC)
    mem = Memory(key=key, content=f"content for {key}", created_at=now, updated_at=now, tags=tags)
    return SearchResult(memory=mem, score=score, source="hybrid")


def _make_query(text: str) -> SearchQuery:
    return SearchQuery(text=text)


# ---------------------------------------------------------------------------
# TopicAffinityRanker
# ---------------------------------------------------------------------------


class TestTopicAffinityRanker:
    def test_boosts_matching_type_tag(self):
        ranker = TopicAffinityRanker(bonus=0.1)
        results = [
            _make_result("a", tags=["problem"], score=0.4),
            _make_result("b", tags=["decision"], score=0.4),
            _make_result("c", tags=["problem", "important"], score=0.3),
        ]
        query = _make_query("There is a bug that keeps crashing, doesn't work")
        ranked = ranker.rank(results, query)
        # problem-tagged memories should be boosted above the decision one
        keys = [r.memory.key for r in ranked]
        assert keys[0] in ("a", "c"), "problem-tagged result should rank highest"
        assert "b" not in keys[:2] or keys[0] != "b", "decision-tagged should not be at top"

    def test_no_boost_when_query_unclassified(self):
        ranker = TopicAffinityRanker(bonus=0.1)
        results = [
            _make_result("x", tags=["preference"], score=0.5),
            _make_result("y", tags=["decision"], score=0.3),
        ]
        # Neutral query — classifier returns None → no change
        query = _make_query("the sky is blue today")
        ranked = ranker.rank(results, query)
        # Original order preserved (scores unchanged)
        assert ranked[0].memory.key == "x"
        assert ranked[1].memory.key == "y"
        # Scores unchanged
        assert ranked[0].score == 0.5
        assert ranked[1].score == 0.3

    def test_empty_results_returns_empty(self):
        ranker = TopicAffinityRanker()
        assert ranker.rank([], _make_query("anything")) == []

    def test_no_tags_memory_not_boosted(self):
        ranker = TopicAffinityRanker(bonus=0.15)
        results = [
            _make_result("notag", tags=[], score=0.5),
            _make_result("pref", tags=["preference"], score=0.4),
        ]
        query = _make_query("I always use snake_case for python variables")
        ranked = ranker.rank(results, query)
        # "pref" boosted by 0.15 → 0.55, overtakes "notag" at 0.5
        assert ranked[0].memory.key == "pref"

    def test_preserves_scores_for_non_matching(self):
        ranker = TopicAffinityRanker(bonus=0.1)
        results = [
            _make_result("m", tags=["milestone"], score=0.6),
        ]
        query = _make_query("There is a bug causing crashes and errors")
        ranked = ranker.rank(results, query)
        # milestone does not match problem — score unchanged
        assert ranked[0].score == 0.6


# ---------------------------------------------------------------------------
# ConvoImporter — parse_conversation_file
# ---------------------------------------------------------------------------


class TestParseClaudeCodeJSONL:
    def test_extracts_user_messages(self, tmp_path: Path):
        data = [
            {"type": "user", "message": {"role": "user", "content": "I always prefer pytest over unittest for testing"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Sure, noted."}]}},
            {"type": "user", "message": {"role": "user", "content": "There is a bug in the search engine that needs to be fixed"}},
        ]
        p = tmp_path / "conv.jsonl"
        p.write_text("\n".join(json.dumps(d) for d in data), encoding="utf-8")
        msgs = parse_conversation_file(str(p))
        contents = [m.content for m in msgs]
        assert any("pytest" in c for c in contents)
        assert any("bug" in c for c in contents)
        # assistant messages should be excluded
        assert not any("Sure, noted" in c for c in contents)

    def test_skips_trivial_messages(self, tmp_path: Path):
        data = [
            {"type": "user", "message": {"role": "user", "content": "ok"}},
            {"type": "user", "message": {"role": "user", "content": "yes"}},
            {"type": "user", "message": {"role": "user", "content": "I decided to use Redis as the caching backend for this project"}},
        ]
        p = tmp_path / "conv.jsonl"
        p.write_text("\n".join(json.dumps(d) for d in data), encoding="utf-8")
        msgs = parse_conversation_file(str(p))
        assert len(msgs) == 1
        assert "Redis" in msgs[0].content

    def test_truncates_very_long_messages(self, tmp_path: Path):
        long_content = "A" * 5000
        data = [{"type": "user", "message": {"role": "user", "content": long_content}}]
        p = tmp_path / "conv.jsonl"
        p.write_text(json.dumps(data[0]), encoding="utf-8")
        msgs = parse_conversation_file(str(p))
        if msgs:
            assert len(msgs[0].content) <= 4000


class TestParseClaudeAiJSON:
    def test_single_conversation_format(self, tmp_path: Path):
        data = {
            "messages": [
                {"role": "human", "content": "I prefer functional programming over OOP for most tasks"},
                {"role": "assistant", "content": "Great choice for many scenarios!"},
                {"role": "human", "content": "The deployment failed because of a missing environment variable"},
            ]
        }
        p = tmp_path / "conv.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        msgs = parse_conversation_file(str(p))
        contents = [m.content for m in msgs]
        assert any("functional" in c for c in contents)
        assert any("deployment" in c for c in contents)
        assert not any("Great choice" in c for c in contents)

    def test_multi_conversation_format(self, tmp_path: Path):
        data = {
            "conversations": [
                {"messages": [{"role": "human", "content": "We decided to switch to TypeScript for better type safety"}]},
                {"messages": [{"role": "human", "content": "The CI pipeline keeps failing due to a flaky test"}]},
            ]
        }
        p = tmp_path / "export.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        msgs = parse_conversation_file(str(p))
        assert len(msgs) == 2


class TestParseChatGPTJSON:
    def test_basic_chatgpt_format(self, tmp_path: Path):
        data = [
            {
                "title": "Test chat",
                "mapping": {
                    "msg1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["I always commit with conventional commit messages"]},
                            "create_time": 1700000000,
                        }
                    },
                    "msg2": {
                        "message": {
                            "author": {"role": "assistant"},
                            "content": {"parts": ["Good practice!"]},
                        }
                    },
                },
            }
        ]
        p = tmp_path / "conversations.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        msgs = parse_conversation_file(str(p))
        assert len(msgs) == 1
        assert "conventional commit" in msgs[0].content


class TestParseErrors:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_conversation_file("/nonexistent/path/conv.json")

    def test_invalid_json(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_conversation_file(str(p))

    def test_unknown_format(self, tmp_path: Path):
        # Valid JSON but unrecognised structure
        data = {"foo": "bar", "baz": [1, 2, 3]}
        p = tmp_path / "unknown.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="Unknown conversation format"):
            parse_conversation_file(str(p))
