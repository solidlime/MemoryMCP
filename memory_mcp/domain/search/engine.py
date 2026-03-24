from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from memory_mcp.domain.shared.errors import SearchError
from memory_mcp.domain.shared.result import Failure, Result, Success

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
        """Execute search based on query mode."""
        if query.mode == "keyword":
            return self._keyword_search(query)
        elif query.mode == "semantic":
            return self._semantic_search(query)
        elif query.mode in ("hybrid", "smart"):
            return self._hybrid_search(query)
        else:
            return Failure(SearchError(f"Unknown search mode: {query.mode}"))

    def _keyword_search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Execute keyword-only search."""
        result = self._keyword.search(query.text, limit=query.top_k)
        if not result.is_ok:
            return Failure(result.error)
        return Success(result.value)

    def _semantic_search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Execute semantic-only search."""
        if self._semantic is None:
            return Failure(SearchError("Semantic search unavailable: no vector store configured"))
        result = self._semantic.search(query.text, limit=query.top_k)
        if not result.is_ok:
            return Failure(result.error)
        return Success(result.value)

    def _hybrid_search(self, query: SearchQuery) -> Result[list[SearchResult], SearchError]:
        """Execute hybrid search combining keyword and semantic results."""
        all_results: list[SearchResult] = []

        kw_result = self._keyword.search(query.text, limit=query.top_k)
        if kw_result.is_ok:
            all_results.extend(kw_result.value)

        if self._semantic is not None:
            sem_result = self._semantic.search(query.text, limit=query.top_k)
            if sem_result.is_ok:
                all_results.extend(sem_result.value)

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
