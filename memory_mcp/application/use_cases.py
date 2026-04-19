from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.domain.equipment.service import EquipmentService
from memory_mcp.domain.memory.service import MemoryService
from memory_mcp.domain.persona.service import PersonaService
from memory_mcp.domain.search.engine import SearchEngine
from memory_mcp.domain.search.ranker import ChainedRanker, ForgettingCurveRanker, RRFRanker, TopicAffinityRanker
from memory_mcp.domain.shared.errors import SearchError
from memory_mcp.domain.shared.result import Failure, Success
from memory_mcp.infrastructure.embedding.model import EmbeddingModel
from memory_mcp.infrastructure.qdrant.adapter import QdrantVectorStore
from memory_mcp.infrastructure.qdrant.client import QdrantClientManager
from memory_mcp.infrastructure.sqlite.connection import SQLiteConnection
from memory_mcp.infrastructure.sqlite.entity_repo import SQLiteEntityRepository
from memory_mcp.infrastructure.sqlite.equipment_repo import SQLiteEquipmentRepository
from memory_mcp.infrastructure.sqlite.memory_repo import SQLiteMemoryRepository
from memory_mcp.infrastructure.sqlite.persona_repo import SQLitePersonaRepository

if TYPE_CHECKING:
    from memory_mcp.config.settings import Settings
    from memory_mcp.infrastructure.embedding.reranker import RerankerModel


class SQLiteKeywordSearch:
    """Adapter: SQLiteMemoryRepository -> KeywordSearchStrategy Protocol."""

    def __init__(self, repo: SQLiteMemoryRepository) -> None:
        self.repo = repo

    def search(self, query: str, limit: int = 10):
        result = self.repo.search_keyword(query, limit)
        if result.is_ok:
            return Success(result.value)
        return Failure(SearchError(str(result.error)))


class QdrantSemanticSearch:
    """Adapter: QdrantVectorStore -> SemanticSearchStrategy Protocol."""

    def __init__(self, vector_store: QdrantVectorStore, memory_repo: SQLiteMemoryRepository) -> None:
        self.vector_store = vector_store
        self.memory_repo = memory_repo
        self._persona: str = ""

    def search(self, query: str, limit: int = 10):
        result = self.vector_store.search(self._persona, query, limit)
        if not result.is_ok:
            return Failure(SearchError(str(result.error)))

        search_results: list[tuple] = []
        for key, score in result.value:
            mem_result = self.memory_repo.find_by_key(key)
            if mem_result.is_ok and mem_result.value:
                search_results.append((mem_result.value, score))
        return Success(search_results)


class AppContext:
    """Dependency injection container for the application."""

    def __init__(self, settings: Settings, persona: str) -> None:
        self.settings = settings
        self.persona = persona
        self.connection = SQLiteConnection(settings.data_dir, persona)
        self.connection.initialize_schema()

        # Run pending schema migrations
        from memory_mcp.migration.engine import MigrationEngine
        MigrationEngine(self.connection).run_all()

        # Repositories
        self.memory_repo = SQLiteMemoryRepository(self.connection)
        self.persona_repo = SQLitePersonaRepository(self.connection)
        self.equipment_repo = SQLiteEquipmentRepository(self.connection)
        self.entity_repo = SQLiteEntityRepository(self.connection)

        # Entity graph (optional — never blocks core memory operations)
        # Must be initialized before MemoryService so it can be injected
        from memory_mcp.domain.memory.graph import EntityService

        self.entity_service = EntityService(self.entity_repo)

        # Services
        self.memory_service = MemoryService(self.memory_repo, entity_service=self.entity_service)
        self.persona_service = PersonaService(self.persona_repo)
        self.equipment_service = EquipmentService(self.equipment_repo)

        # Vector store (lazy)
        self._vector_store: QdrantVectorStore | None = None
        self._embedding: EmbeddingModel | None = None
        self._reranker: RerankerModel | None = None
        self._search_engine: SearchEngine | None = None

    @property
    def vector_store(self) -> QdrantVectorStore | None:
        """Lazy-init vector store. Returns None if Qdrant unavailable."""
        if self._vector_store is None:
            try:
                mgr = QdrantClientManager(self.settings.qdrant.url, self.settings.qdrant.api_key)
                if mgr.health_check():
                    emb = self.embedding_model
                    self._vector_store = QdrantVectorStore(mgr, emb, self.settings.qdrant.collection_prefix)
                    self._vector_store.ensure_collection(self.persona)
            except Exception:
                pass
        return self._vector_store

    @property
    def embedding_model(self) -> EmbeddingModel:
        if self._embedding is None:
            self._embedding = EmbeddingModel(self.settings.embedding.model, self.settings.embedding.device)
        return self._embedding

    @property
    def search_engine(self) -> SearchEngine:
        if self._search_engine is None:
            keyword = SQLiteKeywordSearch(self.memory_repo)
            semantic = QdrantSemanticSearch(self.vector_store, self.memory_repo) if self.vector_store else None

            def _strength_lookup(key: str) -> float:
                result = self.memory_repo.get_strength(key)
                if result.is_ok and result.value is not None:
                    return result.value.strength
                return 1.0

            ranker = ChainedRanker(RRFRanker(), ForgettingCurveRanker(_strength_lookup), TopicAffinityRanker())
            self._search_engine = SearchEngine(keyword, semantic, ranker)
        return self._search_engine

    def close(self) -> None:
        self.connection.close()


class AppContextRegistry:
    """Registry managing per-persona AppContext instances."""

    _contexts: dict[str, AppContext] = {}
    _settings: Settings | None = None

    @classmethod
    def configure(cls, settings: Settings) -> None:
        cls._settings = settings

    @classmethod
    def get(cls, persona: str) -> AppContext:
        if persona in cls._contexts:
            return cls._contexts[persona]

        if cls._settings is None:
            from memory_mcp.config.settings import Settings

            cls._settings = Settings()

        ctx = AppContext(cls._settings, persona)
        cls._contexts[persona] = ctx

        if cls._settings.forgetting.enabled:
            from memory_mcp.application.workers.decay_worker import DecayWorker

            decay_worker = DecayWorker(ctx, cls._settings.forgetting.decay_interval_seconds)
            decay_worker.start()

        return ctx

    @classmethod
    def close_all(cls) -> None:
        for ctx in cls._contexts.values():
            ctx.close()
        cls._contexts.clear()
