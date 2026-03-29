"""Tests for SearchEngine, RRFRanker, and ForgettingCurveRanker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from memory_mcp.domain.memory.entities import Memory
from memory_mcp.domain.search.engine import SearchEngine, SearchQuery, SearchResult
from memory_mcp.domain.search.ranker import ForgettingCurveRanker, RRFRanker
from memory_mcp.domain.shared.result import Failure, Success

UTC = UTC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mem(
    key: str,
    content: str = "content",
    importance: float = 0.5,
    emotion: str = "neutral",
    created_at: datetime | None = None,
) -> Memory:
    now = datetime.now(UTC)
    return Memory(
        key=key,
        content=content,
        created_at=created_at or now,
        updated_at=now,
        importance=importance,
        emotion=emotion,
    )


def _result(key: str, score: float, source: str = "keyword", **kwargs) -> SearchResult:
    return SearchResult(memory=_mem(key, **kwargs), score=score, source=source)


# ---------------------------------------------------------------------------
# RRFRanker
# ---------------------------------------------------------------------------


class TestRRFRanker:
    def test_empty_results_returns_empty(self):
        ranker = RRFRanker()
        query = SearchQuery(text="test")
        assert ranker.rank([], query) == []

    def test_single_source_ranking(self):
        ranker = RRFRanker(k=60)
        query = SearchQuery(text="test")
        results = [
            _result("key_a", score=0.9, source="keyword"),
            _result("key_b", score=0.5, source="keyword"),
            _result("key_c", score=0.1, source="keyword"),
        ]
        ranked = ranker.rank(results, query)
        # Higher-scored items should still rank higher via RRF
        assert len(ranked) == 3
        assert ranked[0].memory.key == "key_a"
        assert ranked[-1].memory.key == "key_c"
        for r in ranked:
            assert r.source == "hybrid"

    def test_multi_source_fusion(self):
        ranker = RRFRanker(k=60)
        query = SearchQuery(text="test")
        # key_a appears in both sources → should fuse to higher score
        results = [
            _result("key_a", score=0.9, source="keyword"),
            _result("key_b", score=0.8, source="keyword"),
            _result("key_a", score=0.85, source="semantic"),
            _result("key_c", score=0.7, source="semantic"),
        ]
        ranked = ranker.rank(results, query)
        keys = [r.memory.key for r in ranked]
        # key_a appears in both sources so its fused RRF score should be highest
        assert keys[0] == "key_a"

    def test_importance_weight_applied(self):
        ranker = RRFRanker(k=60)
        query = SearchQuery(text="test", importance_weight=1.0)
        results = [
            _result("key_low", score=0.9, source="keyword", importance=0.1),
            _result("key_high", score=0.5, source="keyword", importance=0.9),
        ]
        ranked = ranker.rank(results, query)
        # key_high has high importance so importance_weight should boost it
        assert ranked[0].memory.key == "key_high"

    def test_recency_weight_boosts_recent_memory(self):
        ranker = RRFRanker(k=60)
        query = SearchQuery(text="test", recency_weight=10.0)
        recent = datetime.now(UTC)
        old = datetime.now(UTC) - timedelta(days=365)
        results = [
            SearchResult(memory=_mem("old_key", created_at=old), score=0.8, source="keyword"),
            SearchResult(memory=_mem("new_key", created_at=recent), score=0.5, source="keyword"),
        ]
        ranked = ranker.rank(results, query)
        # The newer memory should be ranked first due to high recency weight
        assert ranked[0].memory.key == "new_key"

    def test_recency_weight_with_naive_datetime(self):
        """Memory created_at without tzinfo should be handled gracefully."""
        ranker = RRFRanker(k=60)
        query = SearchQuery(text="test", recency_weight=1.0)
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)  # no tzinfo
        results = [
            SearchResult(memory=_mem("key_naive", created_at=naive_dt), score=0.5, source="keyword"),
        ]
        ranked = ranker.rank(results, query)
        assert len(ranked) == 1


# ---------------------------------------------------------------------------
# ForgettingCurveRanker
# ---------------------------------------------------------------------------


class TestForgettingCurveRanker:
    def test_empty_strength_is_passthrough(self):
        ranker = ForgettingCurveRanker(strength_lookup={})
        query = SearchQuery(text="test")
        results = [_result("key_a", score=0.8), _result("key_b", score=0.5)]
        # No strengths → returned unchanged (same content, no score modification)
        ranked = ranker.rank(results, query)
        assert len(ranked) == 2
        assert ranked[0].score == pytest.approx(0.8)
        assert ranked[1].score == pytest.approx(0.5)

    def test_strength_adjusts_scores(self):
        strengths = {"key_a": 1.0, "key_b": 0.2}
        ranker = ForgettingCurveRanker(strength_lookup=strengths)
        query = SearchQuery(text="test")
        results = [
            _result("key_a", score=0.5),
            _result("key_b", score=0.8),
        ]
        ranked = ranker.rank(results, query)
        # key_a: 0.5 * 1.0 = 0.5, key_b: 0.8 * 0.2 = 0.16 → key_a wins
        assert ranked[0].memory.key == "key_a"
        assert abs(ranked[0].score - 0.5) < 1e-6
        assert abs(ranked[1].score - 0.16) < 1e-6

    def test_missing_key_defaults_to_strength_one(self):
        strengths = {"key_a": 0.5}
        ranker = ForgettingCurveRanker(strength_lookup=strengths)
        query = SearchQuery(text="test")
        results = [
            _result("key_a", score=0.8),
            _result("key_b", score=0.6),  # not in strengths → defaults to 1.0
        ]
        ranked = ranker.rank(results, query)
        # key_a: 0.8 * 0.5 = 0.4, key_b: 0.6 * 1.0 = 0.6 → key_b wins
        assert ranked[0].memory.key == "key_b"

    def test_sorted_descending(self):
        strengths = {"k1": 0.3, "k2": 0.9, "k3": 0.6}
        ranker = ForgettingCurveRanker(strength_lookup=strengths)
        query = SearchQuery(text="test")
        results = [_result("k1", score=1.0), _result("k2", score=1.0), _result("k3", score=1.0)]
        ranked = ranker.rank(results, query)
        scores = [r.score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_source_preserved(self):
        strengths = {"key_x": 0.8}
        ranker = ForgettingCurveRanker(strength_lookup=strengths)
        query = SearchQuery(text="test")
        results = [_result("key_x", score=0.5, source="semantic")]
        ranked = ranker.rank(results, query)
        assert ranked[0].source == "semantic"


# ---------------------------------------------------------------------------
# SearchEngine
# ---------------------------------------------------------------------------


def _make_keyword_strategy(pairs: list[tuple[Memory, float]] | None = None, ok: bool = True):
    strat = MagicMock()
    if ok:
        strat.search.return_value = Success(pairs or [])
    else:
        from memory_mcp.domain.shared.errors import SearchError

        strat.search.return_value = Failure(SearchError("keyword error"))
    return strat


def _make_semantic_strategy(pairs: list[tuple[Memory, float]] | None = None, ok: bool = True):
    strat = MagicMock()
    if ok:
        strat.search.return_value = Success(pairs or [])
    else:
        from memory_mcp.domain.shared.errors import SearchError

        strat.search.return_value = Failure(SearchError("semantic error"))
    return strat


class TestSearchEngineSearch:
    def test_keyword_mode(self):
        mem = _mem("k1", content="hello")
        kw = _make_keyword_strategy([(mem, 0.7)])
        engine = SearchEngine(keyword_search=kw)
        result = engine.search(SearchQuery(text="hello", mode="keyword"))
        assert result.is_ok
        assert len(result.value) == 1
        assert result.value[0].source == "keyword"
        kw.search.assert_called_once_with("hello", limit=5)

    def test_semantic_mode(self):
        mem = _mem("k2", content="hello")
        sem = _make_semantic_strategy([(mem, 0.9)])
        kw = _make_keyword_strategy()
        engine = SearchEngine(keyword_search=kw, semantic_search=sem)
        result = engine.search(SearchQuery(text="hello", mode="semantic"))
        assert result.is_ok
        assert len(result.value) == 1
        assert result.value[0].source == "semantic"

    def test_semantic_mode_without_vector_store_returns_failure(self):
        kw = _make_keyword_strategy()
        engine = SearchEngine(keyword_search=kw, semantic_search=None)
        result = engine.search(SearchQuery(text="hello", mode="semantic"))
        assert not result.is_ok

    def test_hybrid_mode_combines_results(self):
        mem_kw = _mem("kw_key")
        mem_sem = _mem("sem_key")
        kw = _make_keyword_strategy([(mem_kw, 0.7)])
        sem = _make_semantic_strategy([(mem_sem, 0.8)])
        engine = SearchEngine(keyword_search=kw, semantic_search=sem)
        result = engine.search(SearchQuery(text="hello", mode="hybrid", top_k=10))
        assert result.is_ok
        keys = {r.memory.key for r in result.value}
        assert "kw_key" in keys
        assert "sem_key" in keys

    def test_hybrid_mode_deduplicates(self):
        mem = _mem("shared_key")
        kw = _make_keyword_strategy([(mem, 0.7)])
        sem = _make_semantic_strategy([(mem, 0.9)])
        engine = SearchEngine(keyword_search=kw, semantic_search=sem)
        result = engine.search(SearchQuery(text="hello", mode="hybrid", top_k=10))
        assert result.is_ok
        assert sum(1 for r in result.value if r.memory.key == "shared_key") == 1

    def test_unknown_mode_falls_back_to_hybrid(self):
        mem_kw = _mem("kw_key")
        kw = _make_keyword_strategy([(mem_kw, 0.5)])
        sem = _make_semantic_strategy()
        engine = SearchEngine(keyword_search=kw, semantic_search=sem)
        result = engine.search(SearchQuery(text="hello", mode="bogus_mode"))
        assert result.is_ok

    def test_smart_mode_falls_back_to_hybrid(self):
        mem_kw = _mem("kw_key")
        kw = _make_keyword_strategy([(mem_kw, 0.5)])
        engine = SearchEngine(keyword_search=kw)
        result = engine.search(SearchQuery(text="hello", mode="smart"))
        assert result.is_ok

    def test_hybrid_empty_results(self):
        kw = _make_keyword_strategy([])
        sem = _make_semantic_strategy([])
        engine = SearchEngine(keyword_search=kw, semantic_search=sem)
        result = engine.search(SearchQuery(text="hello", mode="hybrid"))
        assert result.is_ok
        assert result.value == []

    def test_hybrid_uses_ranker_when_provided(self):
        mem_kw = _mem("k1")
        mem_sem = _mem("k2")
        kw = _make_keyword_strategy([(mem_kw, 0.5)])
        sem = _make_semantic_strategy([(mem_sem, 0.8)])
        ranker = MagicMock()
        combined = [
            SearchResult(memory=mem_sem, score=0.9, source="semantic"),
            SearchResult(memory=mem_kw, score=0.5, source="keyword"),
        ]
        ranker.rank.return_value = combined
        engine = SearchEngine(keyword_search=kw, semantic_search=sem, ranker=ranker)
        result = engine.search(SearchQuery(text="hello", mode="hybrid"))
        assert result.is_ok
        ranker.rank.assert_called_once()

    def test_keyword_failure_propagates(self):
        kw = _make_keyword_strategy(ok=False)
        engine = SearchEngine(keyword_search=kw)
        result = engine.search(SearchQuery(text="hello", mode="keyword"))
        assert not result.is_ok

    def test_top_k_limits_hybrid_results(self):
        mems = [_mem(f"key_{i}") for i in range(10)]
        pairs = [(m, float(i) / 10) for i, m in enumerate(mems)]
        kw = _make_keyword_strategy(pairs)
        engine = SearchEngine(keyword_search=kw)
        result = engine.search(SearchQuery(text="test", mode="hybrid", top_k=3))
        assert result.is_ok
        assert len(result.value) <= 3


class TestSearchEngineFilterByEmotion:
    def test_no_emotion_filter_returns_all(self):
        results = [
            _result("k1", score=1.0, emotion="joy"),
            _result("k2", score=0.9, emotion="sadness"),
        ]
        out = SearchEngine._filter_by_emotion(results, None)
        assert out == results

    def test_matching_emotion_kept(self):
        results = [
            _result("k1", score=1.0, emotion="joy"),
            _result("k2", score=0.9, emotion="sadness"),
        ]
        out = SearchEngine._filter_by_emotion(results, "joy")
        assert len(out) == 1
        assert out[0].memory.key == "k1"

    def test_no_match_returns_empty(self):
        results = [_result("k1", score=1.0, emotion="sadness")]
        out = SearchEngine._filter_by_emotion(results, "joy")
        assert out == []

    def test_emotion_normalization(self):
        """normalize_emotion should allow keyword synonyms to match."""
        results = [_result("k1", score=1.0, emotion="happy")]
        # "joy" and "happy" normalize to the same canonical value
        out = SearchEngine._filter_by_emotion(results, "joy")
        assert len(out) == 1
