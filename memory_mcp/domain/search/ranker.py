from __future__ import annotations

from datetime import UTC
from typing import Protocol, runtime_checkable

from memory_mcp.domain.search.engine import SearchQuery, SearchResult


@runtime_checkable
class ResultRanker(Protocol):
    """Protocol for result ranking strategies."""

    def rank(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]: ...


class RRFRanker:
    """Reciprocal Rank Fusion ranker."""

    def __init__(self, k: int = 60) -> None:
        self.k = k

    def rank(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Rank results using RRF formula: score = sum(1/(k + rank_i))."""
        if not results:
            return []

        # Group by memory key, accumulating RRF scores
        scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        # Sort each source group by original score to get ranks
        by_source: dict[str, list[SearchResult]] = {}
        for r in results:
            by_source.setdefault(r.source, []).append(r)

        for _source, group in by_source.items():
            group.sort(key=lambda x: x.score, reverse=True)
            for rank, r in enumerate(group):
                key = r.memory.key
                rrf_score = 1.0 / (self.k + rank + 1)
                scores[key] = scores.get(key, 0.0) + rrf_score
                if key not in result_map or r.score > result_map[key].score:
                    result_map[key] = r

        # Apply importance and recency weight adjustments
        merged: list[SearchResult] = []
        for key, rrf_score in scores.items():
            original = result_map[key]
            adjusted_score = rrf_score

            if query.importance_weight > 0:
                adjusted_score += query.importance_weight * original.memory.importance

            if query.recency_weight > 0 and original.memory.created_at:
                from datetime import datetime
                now = datetime.now(UTC)
                created = original.memory.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                age_days = (now - created).total_seconds() / 86400
                recency_bonus = 1.0 / (1.0 + age_days)
                adjusted_score += query.recency_weight * recency_bonus

            merged.append(SearchResult(
                memory=original.memory,
                score=adjusted_score,
                source="hybrid",
            ))

        merged.sort(key=lambda x: x.score, reverse=True)
        return merged


class ForgettingCurveRanker:
    """Adjusts search scores based on Ebbinghaus forgetting curve."""

    def __init__(
        self,
        strength_lookup: dict[str, float] | None = None,
    ) -> None:
        self._strengths = strength_lookup or {}

    def rank(
        self, results: list[SearchResult], query: SearchQuery
    ) -> list[SearchResult]:
        """Multiply scores by recall probability if strength data exists."""
        if not self._strengths:
            return results

        adjusted: list[SearchResult] = []
        for r in results:
            recall = self._strengths.get(r.memory.key, 1.0)
            adjusted.append(SearchResult(
                memory=r.memory,
                score=r.score * recall,
                source=r.source,
            ))
        adjusted.sort(key=lambda x: x.score, reverse=True)
        return adjusted
