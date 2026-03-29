from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from memory_mcp.domain.shared.errors import SearchError
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.domain.value_objects import normalize_emotion

if TYPE_CHECKING:
    from memory_mcp.domain.memory.entities import Memory
    from memory_mcp.domain.search.ranker import ResultRanker
    from memory_mcp.domain.search.strategies import (
        KeywordSearchStrategy,
        SemanticSearchStrategy,
    )


@dataclass
class SearchQuery:
    """Search query parameters."""

    text: str
    mode: str = "hybrid"
    top_k: int = 5
    tags: list[str] | None = None
    date_range: str | None = None
    min_importance: float | None = None
    emotion: str | None = None
    importance_weight: float = 0.0
    recency_weight: float = 0.0


@dataclass
class SearchResult:
    """A single search result with score and source info."""

    memory: Memory
    score: float
    source: str  # "semantic" | "keyword" | "hybrid"


class SearchEngine:
    """Orchestrates search strategies and produces ranked results."""

    def __init__(
        self,
        keyword_search: KeywordSearchStrategy,
        semantic_search: SemanticSearchStrategy | None = None,
        ranker: ResultRanker | None = None,
    ) -> None:
        self._keyword = keyword_search
        self._semantic = semantic_search
        self._ranker = ranker

    def search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Execute search using the specified mode.

        Modes:
            - ``hybrid`` (default): Keyword + semantic RRF fusion. Falls back to keyword-only
              if no vector store is configured.
            - ``keyword``: SQLite keyword search only (fast, exact matches).
            - ``semantic``: Qdrant vector search only (semantic similarity).
            - ``smart``: Query expansion + multi-pass hybrid search merged with RRF.
            - Any other value: falls back to hybrid.
        """
        mode = query.mode or "hybrid"
        if mode == "keyword":
            result = self._keyword_search(query)
        elif mode == "semantic":
            result = self._semantic_search(query)
        elif mode == "smart":
            result = self._smart_search(query)
        else:
            result = self._hybrid_search(query)

        if not result.is_ok:
            return result
        return Success(self._filter_by_emotion(result.value, query.emotion))

    @staticmethod
    def _filter_by_emotion(
        results: list[SearchResult],
        emotion: str | None,
    ) -> list[SearchResult]:
        """Post-filter results by emotion using normalized comparison."""
        if emotion is None:
            return results
        target = normalize_emotion(emotion)
        return [r for r in results if normalize_emotion(r.memory.emotion) == target]

    @staticmethod
    def _to_search_results(
        pairs: list[tuple[Memory, float]],
        source: str,
    ) -> list[SearchResult]:
        """Convert (Memory, score) tuples from strategies into SearchResult objects."""
        return [SearchResult(memory=m, score=s, source=source) for m, s in pairs]

    def _keyword_search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Execute keyword-only search."""
        result = self._keyword.search(query.text, limit=query.top_k)
        if not result.is_ok:
            return Failure(result.error)
        return Success(self._to_search_results(result.value, "keyword"))

    def _semantic_search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Execute semantic-only search."""
        if self._semantic is None:
            return Failure(SearchError("Semantic search unavailable: no vector store configured"))
        result = self._semantic.search(query.text, limit=query.top_k)
        if not result.is_ok:
            return Failure(result.error)
        return Success(self._to_search_results(result.value, "semantic"))

    def _hybrid_search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Execute hybrid search combining keyword and semantic results."""
        all_results: list[SearchResult] = []

        kw_result = self._keyword.search(query.text, limit=query.top_k)
        if kw_result.is_ok:
            all_results.extend(self._to_search_results(kw_result.value, "keyword"))

        if self._semantic is not None:
            sem_result = self._semantic.search(query.text, limit=query.top_k)
            if sem_result.is_ok:
                all_results.extend(self._to_search_results(sem_result.value, "semantic"))

        if not all_results:
            return Success([])

        if self._ranker is not None:
            all_results = self._ranker.rank(all_results, query)
        else:
            all_results.sort(key=lambda x: x.score, reverse=True)

        # Deduplicate by memory key, keeping highest score
        seen: dict[str, SearchResult] = {}
        for r in all_results:
            if r.memory.key not in seen or r.score > seen[r.memory.key].score:
                seen[r.memory.key] = r
        deduped = sorted(seen.values(), key=lambda x: x.score, reverse=True)

        return Success(deduped[: query.top_k])

    def _smart_search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Smart search: hybrid search with simple query expansion.

        Runs the original query plus extracted sub-queries, then merges
        results using RRF to surface the most relevant memories.
        """
        all_results: list[SearchResult] = []

        # 1. Run the original hybrid search
        original = self._hybrid_search(query)
        if original.is_ok:
            all_results.extend(original.value)

        # 2. Generate expanded sub-queries and run additional searches
        sub_queries = _expand_query(query.text)
        for sub_q in sub_queries:
            if sub_q == query.text:
                continue
            sub = SearchQuery(
                text=sub_q,
                top_k=query.top_k,
                mode="hybrid",
                tags=query.tags,
                date_range=query.date_range,
                min_importance=query.min_importance,
                importance_weight=query.importance_weight,
                recency_weight=query.recency_weight,
            )
            result = self._hybrid_search(sub)
            if result.is_ok:
                all_results.extend(result.value)

        if not all_results:
            return Success([])

        # 3. Re-rank merged results with RRF
        if self._ranker is not None:
            all_results = self._ranker.rank(all_results, query)
        else:
            all_results.sort(key=lambda x: x.score, reverse=True)

        # Deduplicate by memory key, keeping highest score
        seen: dict[str, SearchResult] = {}
        for r in all_results:
            if r.memory.key not in seen or r.score > seen[r.memory.key].score:
                seen[r.memory.key] = r
        deduped = sorted(seen.values(), key=lambda x: x.score, reverse=True)
        return Success(deduped[: query.top_k])


def _expand_query(text: str) -> list[str]:
    """Extract sub-queries from text for smart search expansion.

    Splits on Japanese punctuation and whitespace, keeping segments longer
    than 2 characters as additional search queries alongside the original.
    """
    # Split on spaces, Japanese commas/periods, brackets, and common separators
    # \\s = regex whitespace; \uXXXX = actual Unicode chars resolved by Python
    segments = re.split('[\\s\u3000\u3001\u3002\uff0c\uff0e\u300c\u300d\u3010\u3011()\uff08\uff09\uff3b\uff3d]+', text)
    expanded = [text]  # always include original
    for seg in segments:
        seg = seg.strip()
        if len(seg) >= 2 and seg != text:
            expanded.append(seg)
    return expanded[:4]  # limit to 4 queries max
