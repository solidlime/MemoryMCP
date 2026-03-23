from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    import numpy as np
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)

_QUERY_PREFIX = "検索クエリ: "
_DOCUMENT_PREFIX = "検索文書: "


class EmbeddingModel:
    """Lazy-loading embedding model wrapper for sentence-transformers.

    Supports the ruri-v3 family that uses query/document prefixes.
    """

    def __init__(
        self,
        model_name: str = "cl-nagoya/ruri-v3-30m",
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        """Return the embedding dimension, loading the model if needed."""
        if self._dimension is None:
            self._load_model()
        assert self._dimension is not None
        return self._dimension

    def encode(self, text: str, *, is_query: bool = False) -> np.ndarray:
        """Encode a single text to a normalised vector.

        Args:
            text: The text to encode.
            is_query: If True, prepend the query prefix; otherwise the document prefix.
        """
        if self._model is None:
            self._load_model()
        assert self._model is not None
        prefixed = f"{_QUERY_PREFIX}{text}" if is_query else f"{_DOCUMENT_PREFIX}{text}"
        return self._model.encode(prefixed, normalize_embeddings=True)

    def encode_batch(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
        batch_size: int = 32,
    ) -> np.ndarray:
        """Encode multiple texts to normalised vectors.

        Args:
            texts: List of texts to encode.
            is_query: If True, prepend query prefix; otherwise document prefix.
            batch_size: Batch size for encoding.
        """
        if self._model is None:
            self._load_model()
        assert self._model is not None
        prefix = _QUERY_PREFIX if is_query else _DOCUMENT_PREFIX
        prefixed = [f"{prefix}{t}" for t in texts]
        return self._model.encode(
            prefixed, batch_size=batch_size, normalize_embeddings=True
        )

    def _load_model(self) -> None:
        """Lazy load the sentence-transformers model."""
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s (device=%s)", self.model_name, self.device)
        self._model = SentenceTransformer(self.model_name, device=self.device)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Embedding model loaded: dim=%d, model=%s", self._dimension, self.model_name
        )
