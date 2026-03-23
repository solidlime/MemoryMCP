from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = get_logger(__name__)


class RerankerModel:
    """Lazy-loading reranker model for search result refinement."""

    def __init__(
        self,
        model_name: str = "hotchpotch/japanese-reranker-xsmall-v2",
        enabled: bool = True,
    ) -> None:
        self.model_name = model_name
        self.enabled = enabled
        self._model: CrossEncoder | None = None

    def rerank(
        self,
        query: str,
        results: list[tuple[str, float]],
        contents: dict[str, str],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Rerank results using a cross-encoder model.

        Args:
            query: The search query.
            results: List of (key, score) from initial search.
            contents: Mapping of key -> content for reranking.
            top_k: Number of results to return.

        Returns:
            Reranked list of (key, score).
        """
        if not self.enabled or not results:
            return results[:top_k]

        if self._model is None:
            self._load_model()
        assert self._model is not None

        # Build query-document pairs for keys that have content available
        valid_entries: list[tuple[str, float]] = []
        pairs: list[tuple[str, str]] = []
        for key, original_score in results:
            if key in contents:
                pairs.append((query, contents[key]))
                valid_entries.append((key, original_score))

        if not pairs:
            return results[:top_k]

        try:
            scores = self._model.predict(pairs)
        except Exception as e:
            logger.warning("Reranker prediction failed, returning original order: %s", e)
            return results[:top_k]

        # Combine reranker scores with original scores (weighted blend)
        combined: list[tuple[str, float]] = []
        for (key, original_score), rerank_score in zip(valid_entries, scores, strict=True):
            blended = float(rerank_score) * 0.7 + original_score * 0.3
            combined.append((key, blended))

        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:top_k]

    def _load_model(self) -> None:
        """Lazy load the cross-encoder model."""
        from sentence_transformers import CrossEncoder

        logger.info("Loading reranker model: %s", self.model_name)
        self._model = CrossEncoder(self.model_name)
        logger.info("Reranker model loaded: %s", self.model_name)
