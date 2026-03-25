from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from memory_mcp.domain.shared.errors import VectorStoreError
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.infrastructure.embedding.model import EmbeddingModel
    from memory_mcp.infrastructure.qdrant.client import QdrantClientManager

logger = get_logger(__name__)


class QdrantVectorStore:
    """Vector store adapter for memory search using Qdrant."""

    def __init__(
        self,
        client_manager: QdrantClientManager,
        embedding_model: EmbeddingModel,
        collection_prefix: str = "memory_",
    ) -> None:
        self.client_manager = client_manager
        self.embedding = embedding_model
        self.collection_prefix = collection_prefix

    def collection_name(self, persona: str) -> str:
        """Get the collection name for a persona."""
        return f"{self.collection_prefix}{persona}"

    def ensure_collection(self, persona: str) -> Result[None, VectorStoreError]:
        """Create the Qdrant collection for a persona if it does not exist."""
        name = self.collection_name(persona)
        try:
            from qdrant_client.models import Distance, VectorParams

            collections = self.client_manager.client.get_collections().collections
            if not any(c.name == name for c in collections):
                self.client_manager.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=self.embedding.dimension,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection: %s", name)
            return Success(None)
        except Exception as e:
            err_str = str(e)
            if "No such file or directory" in err_str or "storage" in err_str.lower():
                logger.error(
                    "Failed to ensure collection %s: %s\n"
                    "HINT: Qdrant's storage directory is missing. "
                    "Run via `docker-compose up -d` so the ./data/qdrant volume is mounted, "
                    "or pre-create the storage directory before starting Qdrant standalone.",
                    name,
                    e,
                )
            else:
                logger.error("Failed to ensure collection %s: %s", name, e)
            return Failure(VectorStoreError(str(e)))

    def upsert(
        self,
        persona: str,
        key: str,
        content: str,
        metadata: dict | None = None,
    ) -> Result[None, VectorStoreError]:
        """Embed and upsert a memory into the vector store."""
        try:
            from qdrant_client.models import PointStruct

            vector = self.embedding.encode(content, is_query=False)
            payload = {"key": key, "content": content}
            if metadata:
                payload.update(metadata)

            point = PointStruct(
                id=self._key_to_id(key),
                vector=vector.tolist(),
                payload=payload,
            )
            self.client_manager.client.upsert(
                collection_name=self.collection_name(persona),
                points=[point],
            )
            logger.info("Upserted vector for key: %s", key)
            return Success(None)
        except Exception as e:
            logger.error("Failed to upsert vector for %s: %s", key, e)
            return Failure(VectorStoreError(str(e)))

    def search(self, persona: str, query: str, limit: int = 10) -> Result[list[tuple[str, float]], VectorStoreError]:
        """Semantic search. Returns list of (memory_key, score)."""
        try:
            vector = self.embedding.encode(query, is_query=True)
            response = self.client_manager.client.query_points(
                collection_name=self.collection_name(persona),
                query=vector.tolist(),
                limit=limit,
            )
            results = response.points
            return Success([(r.payload["key"], r.score) for r in results])
        except Exception as e:
            logger.error("Failed to search vectors for '%s': %s", query, e)
            return Failure(VectorStoreError(str(e)))

    def delete(self, persona: str, key: str) -> Result[None, VectorStoreError]:
        """Delete a point from the vector store."""
        try:
            from qdrant_client.models import PointIdsList

            self.client_manager.client.delete(
                collection_name=self.collection_name(persona),
                points_selector=PointIdsList(points=[self._key_to_id(key)]),
            )
            logger.info("Deleted vector for key: %s", key)
            return Success(None)
        except Exception as e:
            logger.error("Failed to delete vector for %s: %s", key, e)
            return Failure(VectorStoreError(str(e)))

    def count(self, persona: str) -> Result[int, VectorStoreError]:
        """Count points in the persona's collection."""
        try:
            info = self.client_manager.client.get_collection(collection_name=self.collection_name(persona))
            return Success(info.points_count)
        except Exception as e:
            logger.error("Failed to count vectors for '%s': %s", persona, e)
            return Failure(VectorStoreError(str(e)))

    def upsert_batch(
        self,
        persona: str,
        memories: list[tuple[str, str]],
        batch_size: int = 64,
    ) -> Result[int, VectorStoreError]:
        """Batch upsert multiple memories. Returns count of upserted points."""
        if not memories:
            return Success(0)
        try:
            from qdrant_client.models import PointStruct

            contents = [content for _, content in memories]
            vectors = self.embedding.encode_batch(contents, is_query=False)
            total = 0
            for i in range(0, len(memories), batch_size):
                batch = memories[i : i + batch_size]
                batch_vectors = vectors[i : i + batch_size]
                points = []
                for (key, content), vec in zip(batch, batch_vectors, strict=True):
                    points.append(
                        PointStruct(
                            id=self._key_to_id(key),
                            vector=vec.tolist(),
                            payload={"key": key, "content": content},
                        )
                    )
                self.client_manager.client.upsert(
                    collection_name=self.collection_name(persona),
                    points=points,
                )
                total += len(points)
            logger.info(
                "Batch upserted %d vectors for persona: %s",
                total,
                persona,
            )
            return Success(total)
        except Exception as e:
            logger.error("Failed to batch upsert for '%s': %s", persona, e)
            return Failure(VectorStoreError(str(e)))

    def rebuild_collection(self, persona: str) -> Result[None, VectorStoreError]:
        """Delete and recreate collection for a persona."""
        name = self.collection_name(persona)
        try:
            try:
                self.client_manager.client.delete_collection(name)
                logger.info("Deleted collection: %s", name)
            except Exception:
                logger.debug(
                    "Collection %s did not exist, skipping delete",
                    name,
                )
            return self.ensure_collection(persona)
        except Exception as e:
            logger.error("Failed to rebuild collection '%s': %s", name, e)
            return Failure(VectorStoreError(str(e)))

    @staticmethod
    def _key_to_id(key: str) -> str:
        """Convert a memory key to a deterministic UUID-like hex string for Qdrant."""
        return hashlib.md5(key.encode()).hexdigest()  # noqa: S324

    def reconnect(self, new_url: str | None = None, new_api_key: str | None = None) -> dict:
        """Qdrantクライアントを再接続する。client_managerに委譲。"""
        return self.client_manager.reconnect(new_url=new_url, new_api_key=new_api_key)

    def get_connection_status(self) -> dict:
        """接続状態を返す。client_managerに委譲。"""
        return self.client_manager.get_connection_status()
