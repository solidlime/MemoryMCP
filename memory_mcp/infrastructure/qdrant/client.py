from __future__ import annotations

from memory_mcp.infrastructure.logging.structured import get_logger

logger = get_logger(__name__)


class QdrantClientManager:
    """Manages Qdrant client lifecycle and health checking."""

    def __init__(self, url: str = "http://localhost:6333", api_key: str | None = None) -> None:
        self.url = url
        self.api_key = api_key
        self._client: object | None = None

    @property
    def client(self) -> object:
        """Get or create the Qdrant client (lazy initialization)."""
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url, api_key=self.api_key)
            logger.info("Qdrant client connected to %s", self.url)
        return self._client

    def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.warning("Qdrant health check failed: %s", e)
            return False

    def close(self) -> None:
        """Close the Qdrant client connection."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as e:
                logger.warning("Error closing Qdrant client: %s", e)
            finally:
                self._client = None
