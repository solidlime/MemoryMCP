from __future__ import annotations

import contextlib

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

    def reconnect(self, new_url: str | None = None, new_api_key: str | None = None) -> dict:
        """クライアントを再接続する（スレッドセーフ）。"""
        old_client = self._client
        old_url = self.url
        old_api_key = self.api_key

        if new_url:
            self.url = new_url
        if new_api_key is not None:
            self.api_key = new_api_key

        self._client = None

        try:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url, api_key=self.api_key)
            collections = self._client.get_collections().collections
            # 旧クライアントをクローズ
            if old_client is not None:
                with contextlib.suppress(Exception):
                    old_client.close()
            logger.info("Qdrant reconnected to %s", self.url)
            return {
                "status": "connected",
                "url": self.url,
                "collections": len(collections),
                "message": f"Connected to {self.url}",
            }
        except Exception as e:
            logger.error("Failed to reconnect to Qdrant: %s", e)
            # フォールバック
            self._client = old_client
            self.url = old_url
            self.api_key = old_api_key
            return {
                "status": "error",
                "url": self.url,
                "collections": 0,
                "message": f"Reconnect failed, reverted: {e}",
            }

    def get_connection_status(self) -> dict:
        """接続状態を返す。"""
        if self._client is None:
            return {"status": "disconnected", "url": self.url, "collections": []}
        try:
            collections = self._client.get_collections().collections
            return {
                "status": "connected",
                "url": self.url,
                "collections": [c.name for c in collections],
            }
        except Exception:
            return {"status": "disconnected", "url": self.url, "collections": []}
