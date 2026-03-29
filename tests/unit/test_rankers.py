from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from memory_mcp.domain.search.engine import SearchQuery, SearchResult
from memory_mcp.domain.search.ranker import ChainedRanker, ForgettingCurveRanker, RRFRanker


def _make_result(key: str, score: float, source: str = "keyword") -> SearchResult:
    memory = MagicMock()
    memory.key = key
    memory.importance = 0.5
    memory.created_at = None
    memory.emotion = None
    return SearchResult(memory=memory, score=score, source=source)


class TestForgettingCurveRanker:
    def test_returns_unchanged_when_no_lookup(self) -> None:
        ranker = ForgettingCurveRanker()
        results = [_make_result("a", 1.0), _make_result("b", 0.5)]
        query = SearchQuery(text="test")
        assert ranker.rank(results, query) is results

    def test_dict_lookup_scales_scores(self) -> None:
        ranker = ForgettingCurveRanker({"a": 0.5, "b": 1.0})
        results = [_make_result("a", 1.0), _make_result("b", 1.0)]
        query = SearchQuery(text="test")
        ranked = ranker.rank(results, query)
        scores = {r.memory.key: r.score for r in ranked}
        assert scores["a"] == pytest.approx(0.5)
        assert scores["b"] == pytest.approx(1.0)

    def test_callable_lookup_scales_scores(self) -> None:
        lookup = {"a": 0.25}
        ranker = ForgettingCurveRanker(lambda key: lookup.get(key, 1.0))
        results = [_make_result("a", 2.0), _make_result("b", 2.0)]
        query = SearchQuery(text="test")
        ranked = ranker.rank(results, query)
        scores = {r.memory.key: r.score for r in ranked}
        assert scores["a"] == pytest.approx(0.5)
        assert scores["b"] == pytest.approx(2.0)

    def test_missing_key_defaults_to_1(self) -> None:
        ranker = ForgettingCurveRanker({"x": 0.8})
        results = [_make_result("unknown", 3.0)]
        query = SearchQuery(text="test")
        ranked = ranker.rank(results, query)
        assert ranked[0].score == pytest.approx(3.0)

    def test_sorted_by_score_descending(self) -> None:
        ranker = ForgettingCurveRanker({"a": 0.1, "b": 0.9})
        results = [_make_result("a", 1.0), _make_result("b", 1.0)]
        query = SearchQuery(text="test")
        ranked = ranker.rank(results, query)
        assert ranked[0].memory.key == "b"
        assert ranked[1].memory.key == "a"


class TestChainedRanker:
    def test_applies_rankers_in_order(self) -> None:
        first = MagicMock()
        second = MagicMock()
        results = [_make_result("a", 1.0)]
        intermediate = [_make_result("a", 0.5)]
        final = [_make_result("a", 0.25)]
        first.rank.return_value = intermediate
        second.rank.return_value = final
        query = SearchQuery(text="test")

        chained = ChainedRanker(first, second)
        out = chained.rank(results, query)

        first.rank.assert_called_once_with(results, query)
        second.rank.assert_called_once_with(intermediate, query)
        assert out is final

    def test_empty_rankers_returns_results_unchanged(self) -> None:
        results = [_make_result("a", 1.0)]
        query = SearchQuery(text="test")
        chained = ChainedRanker()
        assert chained.rank(results, query) is results

    def test_rrf_then_forgetting_curve(self) -> None:
        """Integration: RRFRanker followed by ForgettingCurveRanker."""
        r1 = _make_result("mem_strong", 1.0, source="keyword")
        r2 = _make_result("mem_weak", 0.9, source="keyword")
        query = SearchQuery(text="test")

        strengths = {"mem_strong": 1.0, "mem_weak": 0.1}
        chained = ChainedRanker(RRFRanker(), ForgettingCurveRanker(strengths))
        ranked = chained.rank([r1, r2], query)

        # mem_weak should be pushed down due to low recall probability
        assert ranked[0].memory.key == "mem_strong"
        assert ranked[1].memory.key == "mem_weak"
