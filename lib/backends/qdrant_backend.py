import hashlib
from typing import List, Tuple

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest


class _IndexProxy:
    def __init__(self, client: QdrantClient, collection: str):
        self._client = client
        self._collection = collection

    @property
    def ntotal(self) -> int:
        try:
            res = self._client.count(self._collection, exact=True)
            return int(res.count)
        except Exception:
            return 0


def _key_to_point_id(key: str) -> int:
    # Stable 64-bit integer from key
    h = hashlib.sha1(key.encode('utf-8')).digest()
    return int.from_bytes(h[:8], 'big', signed=False)


class QdrantVectorStoreAdapter:
    """
    Minimal adapter to mimic the FAISS interface used in vector_utils.py
    Methods: add_documents, delete, similarity_search_with_score
    Attributes: index.ntotal
    """

    def __init__(self, client: QdrantClient, collection: str, embeddings, dim: int):
        self.client = client
        self.collection = collection
        self.embeddings = embeddings
        self.dim = dim
        self._ensure_collection()
        self.index = _IndexProxy(client, collection)

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection)
        except Exception:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config=rest.VectorParams(size=self.dim, distance=rest.Distance.COSINE),
            )

    def add_documents(self, docs: List[Document], ids: List[str]):
        texts = [d.page_content for d in docs]
        payloads = []
        point_ids = []
        for d, key in zip(docs, ids):
            payloads.append({
                'key': key,
                'content': d.page_content,
                **(d.metadata or {})
            })
            point_ids.append(_key_to_point_id(key))
        vectors = self.embeddings.embed_documents(texts)
        points = [
            rest.PointStruct(id=pid, vector=vec, payload=pl)
            for pid, vec, pl in zip(point_ids, vectors, payloads)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def delete(self, ids: List[str]):
        # Delete by payload filter key in ids
        self.client.delete(
            collection_name=self.collection,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="key",
                            match=rest.MatchAny(any=ids)
                        )
                    ]
                )
            ),
        )

    def similarity_search_with_score(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        vec = self.embeddings.embed_query(query)
        result = self.client.search(
            collection_name=self.collection,
            query_vector=vec,
            limit=k,
            with_payload=True
        )
        out: List[Tuple[Document, float]] = []
        for sp in result:
            payload = sp.payload or {}
            text = payload.get('content', '')
            # 🆕 Phase 26: Preserve all metadata from payload
            metadata = {k: v for k, v in payload.items() if k != 'content'}
            # Convert similarity (higher better) to distance-like (lower better) for compatibility
            distance_like = float(1.0 - (sp.score or 0.0))
            out.append((Document(page_content=text, metadata=metadata), distance_like))
        return out
