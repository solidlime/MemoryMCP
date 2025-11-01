import os
import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer
try:
    from sentence_transformers import CrossEncoder
    CROSSENCODER_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    CROSSENCODER_AVAILABLE = False

from tqdm import tqdm

from config_utils import load_config
try:
    from qdrant_client import QdrantClient
    from lib.backends.qdrant_backend import QdrantVectorStoreAdapter
    QDRANT_AVAILABLE = True
except Exception:
    QDRANT_AVAILABLE = False
from persona_utils import get_db_path, get_vector_store_path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _get_rebuild_config():
    cfg = load_config() or {}
    vr = cfg.get("vector_rebuild", {}) if isinstance(cfg, dict) else {}
    return {
        "mode": vr.get("mode", "idle"),
        "idle_seconds": int(vr.get("idle_seconds", 30)),
        "min_interval": int(vr.get("min_interval", 120)),
    }

# Globals for RAG
vector_store = None
embeddings = None
reranker = None
backend_type = "faiss"
sentiment_pipeline = None  # Phase 19: Sentiment analysis pipeline

# Idle rebuild controls
_dirty: bool = False
_last_write_ts: float = 0.0
_last_rebuild_ts: float = 0.0
_rebuild_lock = threading.Lock()

# Phase 21: Idle cleanup controls
_last_cleanup_check: float = 0.0
_cleanup_lock = threading.Lock()

def mark_vector_store_dirty():
    global _dirty, _last_write_ts
    _dirty = True
    _last_write_ts = time.time()

def start_idle_rebuilder_thread():
    t = threading.Thread(target=_idle_rebuilder_loop, daemon=True)
    t.start()
    return t

def _idle_rebuilder_loop():
    global _dirty, _last_rebuild_ts
    while True:
        try:
            cfg = _get_rebuild_config()
            if cfg.get("mode", "idle") != "idle":
                time.sleep(2)
                continue
            if _dirty:
                now = time.time()
                if (now - _last_write_ts) >= cfg.get("idle_seconds", 30) and (now - _last_rebuild_ts) >= cfg.get("min_interval", 120):
                    with _rebuild_lock:
                        if _dirty:
                            rebuild_vector_store()
                            _dirty = False
                            _last_rebuild_ts = time.time()
            time.sleep(2)
        except Exception:
            time.sleep(5)

# ============================================================================
# Phase 21: Idle Cleanup Worker
# ============================================================================

def _get_cleanup_config():
    """Get auto_cleanup configuration from config.json"""
    cfg = load_config()
    ac = cfg.get("auto_cleanup", {})
    return {
        "enabled": ac.get("enabled", True),
        "idle_minutes": int(ac.get("idle_minutes", 30)),
        "check_interval_seconds": int(ac.get("check_interval_seconds", 300)),
        "duplicate_threshold": float(ac.get("duplicate_threshold", 0.90)),
        "min_similarity_to_report": float(ac.get("min_similarity_to_report", 0.85)),
        "max_suggestions_per_run": int(ac.get("max_suggestions_per_run", 20)),
    }

def start_cleanup_worker_thread():
    """Start background cleanup worker thread"""
    cfg = _get_cleanup_config()
    if not cfg.get("enabled", True):
        return None
    t = threading.Thread(target=_cleanup_worker_loop, daemon=True)
    t.start()
    return t

def _cleanup_worker_loop():
    """Background loop that checks for cleanup opportunities during idle time"""
    global _last_cleanup_check, _last_write_ts
    
    while True:
        try:
            cfg = _get_cleanup_config()
            if not cfg.get("enabled", True):
                time.sleep(60)
                continue
            
            now = time.time()
            check_interval = cfg.get("check_interval_seconds", 300)
            
            # Wait for check interval
            if (now - _last_cleanup_check) < check_interval:
                time.sleep(10)
                continue
            
            # Check if idle (no writes for idle_minutes)
            idle_seconds = cfg.get("idle_minutes", 30) * 60
            if (now - _last_write_ts) < idle_seconds:
                time.sleep(10)
                continue
            
            # Run cleanup check
            with _cleanup_lock:
                _last_cleanup_check = now
                _detect_and_save_cleanup_suggestions(cfg)
            
            # Sleep after successful check
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"⚠️ Cleanup worker error: {e}")
            time.sleep(60)

def _detect_and_save_cleanup_suggestions(cfg):
    """Detect duplicates and save suggestions to file"""
    try:
        from persona_utils import get_current_persona, get_persona_dir
        
        persona = get_current_persona()
        threshold = cfg.get("duplicate_threshold", 0.90)
        max_pairs = cfg.get("max_suggestions_per_run", 20)
        
        print(f"🧹 Running cleanup check for persona: {persona} (threshold: {threshold:.2f})...")
        
        # Detect duplicates
        duplicates = detect_duplicate_memories(threshold, max_pairs)
        
        if not duplicates:
            print(f"✅ No cleanup suggestions (threshold: {threshold:.2f})")
            return
        
        # Group duplicates into suggestion groups
        groups = _create_cleanup_groups(duplicates, cfg)
        
        # Save to file
        persona_dir = get_persona_dir(persona)
        suggestions_file = os.path.join(persona_dir, "cleanup_suggestions.json")
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        timezone = load_config().get("timezone", "Asia/Tokyo")
        now = datetime.now(ZoneInfo(timezone))
        
        suggestions_data = {
            "generated_at": now.isoformat(),
            "persona": persona,
            "total_memories": _count_total_memories(),
            "groups": groups,
            "summary": {
                "total_groups": len(groups),
                "high_priority": sum(1 for g in groups if g["priority"] == "high"),
                "medium_priority": sum(1 for g in groups if g["priority"] == "medium"),
                "low_priority": sum(1 for g in groups if g["priority"] == "low"),
            }
        }
        
        with open(suggestions_file, 'w', encoding='utf-8') as f:
            json.dump(suggestions_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Cleanup suggestions saved: {len(groups)} groups found")
        print(f"   📁 {suggestions_file}")
        
    except Exception as e:
        print(f"❌ Failed to generate cleanup suggestions: {e}")

def _create_cleanup_groups(duplicates, cfg):
    """Create cleanup suggestion groups from duplicate pairs"""
    groups = []
    min_report = cfg.get("min_similarity_to_report", 0.85)
    
    for idx, (key1, key2, content1, content2, similarity) in enumerate(duplicates, 1):
        if similarity < min_report:
            continue
        
        # Determine priority
        if similarity >= 0.99:
            priority = "high"
        elif similarity >= 0.95:
            priority = "medium"
        else:
            priority = "low"
        
        # Create preview (first 100 chars)
        preview = content1[:100] + "..." if len(content1) > 100 else content1
        
        group = {
            "group_id": idx,
            "priority": priority,
            "similarity": round(similarity, 3),
            "memory_keys": [key1, key2],
            "preview": preview,
            "recommended_action": "merge" if similarity >= 0.95 else "review"
        }
        
        groups.append(group)
    
    return groups

def _count_total_memories():
    """Count total memories in current persona"""
    try:
        from persona_utils import get_db_path
        import sqlite3
        
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            return cursor.fetchone()[0]
    except Exception:
        return 0

def _get_embedding_dimension(model_name: str) -> int:
    try:
        m = SentenceTransformer(model_name)
        return int(m.get_sentence_embedding_dimension())
    except Exception:
        return 384


def initialize_rag_sync():
    """Initialize embeddings/reranker and load or bootstrap a vector store."""
    global vector_store, embeddings, reranker, backend_type
    cfg = load_config()
    embeddings_model = cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m")
    embeddings_device = cfg.get("embeddings_device", "cpu")
    reranker_model = cfg.get("reranker_model", "hotchpotch/japanese-reranker-xsmall-v2")
    storage_backend = cfg.get("storage_backend", "sqlite").lower()

    # Embeddings
    try:
        with tqdm(total=100, desc="📥 Embeddings Model", unit="%", ncols=80) as pbar:
            embeddings = HuggingFaceEmbeddings(
                model_name=embeddings_model,
                model_kwargs={'device': embeddings_device},
                encode_kwargs={'normalize_embeddings': True}
            )
            pbar.update(100)
    except Exception:
        embeddings = None

    # Reranker
    if CROSSENCODER_AVAILABLE:
        try:
            with tqdm(total=100, desc="📥 Reranker Model", unit="%", ncols=80) as pbar:
                reranker = CrossEncoder(reranker_model)
                pbar.update(100)
        except Exception:
            reranker = None
    else:
        reranker = None

    # Vector store load or create
    vs_path = get_vector_store_path()
    legacy_vs_path = os.path.join(SCRIPT_DIR, "vector_store")
    if os.path.exists(legacy_vs_path) and not os.path.exists(vs_path):
        try:
            shutil.copytree(legacy_vs_path, vs_path)
        except Exception:
            pass

    if storage_backend == "qdrant" and QDRANT_AVAILABLE and embeddings is not None:
        backend_type = "qdrant"
        dim = _get_embedding_dimension(embeddings_model)
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        from persona_utils import get_current_persona
        collection = f"{prefix}{get_current_persona()}"
        client = QdrantClient(url=url, api_key=api_key)
        vector_store = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        # Bootstrap from SQLite if empty
        try:
            with sqlite3.connect(get_db_path()) as conn:
                cur = conn.cursor()
                cur.execute('SELECT key, content FROM memories')
                rows = cur.fetchall()
            if rows and vector_store.index.ntotal == 0:
                docs = [Document(page_content=c, metadata={"key": k}) for (k, c) in rows]
                vector_store.add_documents(docs, ids=[k for (k, _) in rows])
        except Exception:
            pass
    else:
        backend_type = "faiss"
        if os.path.exists(vs_path) and embeddings is not None:
            try:
                vector_store = FAISS.load_local(vs_path, embeddings, allow_dangerous_deserialization=True)
            except Exception:
                vector_store = None

        if vector_store is None and embeddings is not None:
            # Build from DB if possible
            try:
                with sqlite3.connect(get_db_path()) as conn:
                    cur = conn.cursor()
                    cur.execute('SELECT key, content FROM memories')
                    rows = cur.fetchall()
                if rows:
                    docs = [Document(page_content=c, metadata={"key": k}) for (k, c) in rows]
                    vector_store = FAISS.from_documents(docs, embeddings)
                    save_vector_store()
                else:
                    dummy_doc = Document(page_content="初期化用ダミー", metadata={"key": "dummy"})
                    vector_store = FAISS.from_documents([dummy_doc], embeddings)
                    save_vector_store()
            except Exception:
                # As a last resort, create empty with dummy
                try:
                    dummy_doc = Document(page_content="初期化用ダミー", metadata={"key": "dummy"})
                    vector_store = FAISS.from_documents([dummy_doc], embeddings)
                    save_vector_store()
                except Exception:
                    vector_store = None
    
    # Phase 19: Initialize sentiment analysis
    initialize_sentiment_analysis()

def save_vector_store():
    if vector_store:
        if backend_type == "faiss":
            try:
                vector_store.save_local(get_vector_store_path())
                return True
            except Exception:
                return False
        else:
            # Qdrant persists server-side
            return True
    return False

def rebuild_vector_store():
    global vector_store
    if not embeddings:
        return
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cur = conn.cursor()
            cur.execute('SELECT key, content FROM memories')
            rows = cur.fetchall()
        if not rows:
            return
        docs = [Document(page_content=c, metadata={"key": k}) for (k, c) in rows]
        if backend_type == "faiss":
            with tqdm(total=1, desc="⚙️  Building FAISS Index", unit="index", ncols=80) as pbar:
                vector_store = FAISS.from_documents(docs, embeddings)
                pbar.update(1)
            save_vector_store()
        else:
            # Qdrant: upsert all points
            vector_store.add_documents(docs, ids=[k for (k, _) in rows])
    except Exception:
        pass

def add_memory_to_vector_store(key: str, content: str):
    """
    Add a new memory to the vector store incrementally.
    Falls back to dirty flag if vector store is not available.
    """
    global vector_store
    
    if not vector_store or not embeddings:
        mark_vector_store_dirty()
        return
    
    try:
        # Fetch metadata for richer payload (for Qdrant migration)
        created_at = None
        updated_at = None
        tags_json = None
        try:
            with sqlite3.connect(get_db_path()) as conn:
                cur = conn.cursor()
                cur.execute('SELECT created_at, updated_at, tags FROM memories WHERE key = ?', (key,))
                row = cur.fetchone()
                if row:
                    created_at, updated_at, tags_json = row
        except Exception:
            pass

        meta = {"key": key}
        if created_at:
            meta["created_at"] = created_at
        if updated_at:
            meta["updated_at"] = updated_at
        if tags_json:
            meta["tags"] = tags_json

        # Create document with metadata
        doc = Document(page_content=content, metadata=meta)
        
        # Add to vector store with ID
        vector_store.add_documents([doc], ids=[key])
        
        # Save immediately (FAISS only)
        save_vector_store()
        
        print(f"✅ Added memory {key} to vector store incrementally")
    except Exception as e:
        print(f"⚠️  Failed to add memory incrementally: {e}, falling back to dirty flag")
        mark_vector_store_dirty()

def update_memory_in_vector_store(key: str, content: str):
    """
    Update an existing memory in the vector store incrementally.
    Falls back to dirty flag if vector store is not available.
    """
    global vector_store
    
    if not vector_store or not embeddings:
        mark_vector_store_dirty()
        return
    
    try:
        # Delete old version
        vector_store.delete([key])

        # Fetch metadata (keep original created_at)
        created_at = None
        updated_at = None
        tags_json = None
        try:
            with sqlite3.connect(get_db_path()) as conn:
                cur = conn.cursor()
                cur.execute('SELECT created_at, updated_at, tags FROM memories WHERE key = ?', (key,))
                row = cur.fetchone()
                if row:
                    created_at, updated_at, tags_json = row
        except Exception:
            pass

        meta = {"key": key}
        if created_at:
            meta["created_at"] = created_at
        if updated_at:
            meta["updated_at"] = updated_at
        if tags_json:
            meta["tags"] = tags_json

        # Add new version
        doc = Document(page_content=content, metadata=meta)
        vector_store.add_documents([doc], ids=[key])
        
        # Save immediately (FAISS only)
        save_vector_store()
        
        print(f"✅ Updated memory {key} in vector store incrementally")
    except Exception as e:
        print(f"⚠️  Failed to update memory incrementally: {e}, falling back to dirty flag")
        mark_vector_store_dirty()

def delete_memory_from_vector_store(key: str):
    """
    Delete a memory from the vector store incrementally.
    Falls back to dirty flag if vector store is not available.
    """
    global vector_store
    
    if not vector_store:
        mark_vector_store_dirty()
        return
    
    try:
        # Delete from vector store
        vector_store.delete([key])
        
        # Save immediately
        save_vector_store()
        
        print(f"✅ Deleted memory {key} from vector store incrementally")
    except Exception as e:
        print(f"⚠️  Failed to delete memory incrementally: {e}, falling back to dirty flag")
        mark_vector_store_dirty()

def get_vector_count() -> int:
    try:
        return vector_store.index.ntotal if vector_store else 0
    except Exception:
        return 0

def get_vector_metrics() -> dict:
    """
    Return detailed metrics for monitoring and debugging.
    
    Returns:
        dict with keys:
        - embeddings_model: str (model name or None)
        - embeddings_loaded: bool
        - reranker_model: str (model name or None)
        - reranker_loaded: bool
        - vector_count: int
        - dirty: bool
        - last_write_ts: float (Unix timestamp)
        - last_rebuild_ts: float (Unix timestamp)
        - rebuild_config: dict (mode, idle_seconds, min_interval)
    """
    cfg = load_config()
    rebuild_cfg = _get_rebuild_config()
    
    embeddings_model_name = cfg.get("embeddings_model", "Unknown") if embeddings else None
    reranker_model_name = cfg.get("reranker_model", "Unknown") if reranker else None
    
    return {
        "embeddings_model": embeddings_model_name,
        "embeddings_loaded": embeddings is not None,
        "reranker_model": reranker_model_name,
        "reranker_loaded": reranker is not None,
        "vector_count": get_vector_count(),
        "backend": backend_type,
        "dirty": _dirty,
        "last_write_ts": _last_write_ts,
        "last_rebuild_ts": _last_rebuild_ts,
        "rebuild_config": rebuild_cfg,
    }

def find_similar_memories(query_key: str, top_k: int = 5) -> list:
    """
    Find memories similar to the specified memory using embeddings similarity.
    
    Args:
        query_key: The key of the memory to find similar memories for
        top_k: Number of similar memories to return (default: 5)
        
    Returns:
        List of tuples: [(key, content, score), ...]
        Empty list if query_key not found or vector store not available
    """
    global vector_store
    
    if not vector_store:
        return []
    
    try:
        # Get the content of the query memory from database
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute('SELECT content FROM memories WHERE key = ?', (query_key,))
            row = cur.fetchone()
            
        if not row:
            return []
        
        query_content = row[0]
        
    # Search similar documents
    # top_k + 1 because the query itself will be in results
    results = vector_store.similarity_search_with_score(query_content, k=top_k + 1)
        
        # Filter out the query memory itself and format results
        similar = []
        for doc, score in results:
            key = doc.metadata.get("key")
            if key != query_key:  # Exclude the query memory itself
                # For FAISS (L2): lower distance is better → convert to similarity
                # For Qdrant (cosine): we returned (1 - cosine) to emulate a distance
                similarity = 1.0 / (1.0 + float(score))
                similar.append((key, doc.page_content, similarity))
        
        # Return top_k results (excluding query itself)
        return similar[:top_k]
        
    except Exception as e:
        print(f"Error finding similar memories: {e}")
        return []

def detect_duplicate_memories(threshold: float = 0.85, max_pairs: int = 50) -> list:
    """
    Detect duplicate or highly similar memory pairs using embeddings similarity.
    
    Args:
        threshold: Similarity threshold (0.0-1.0). Pairs above this are considered duplicates.
                  Default 0.85 means 85% similar or more.
        max_pairs: Maximum number of duplicate pairs to return (default: 50)
        
    Returns:
        List of tuples: [(key1, key2, content1, content2, similarity), ...]
        Sorted by similarity (highest first)
    """
    global vector_store
    
    if not vector_store:
        return []
    
    try:
        # Get all memories from database
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute('SELECT key, content FROM memories ORDER BY created_at')
            all_memories = cur.fetchall()
        
        if len(all_memories) < 2:
            return []
        
        duplicate_pairs = []
        
        # Compare each memory with all subsequent memories
        for i in range(len(all_memories)):
            key1, content1 = all_memories[i]
            
            # Search for similar memories
            results = vector_store.similarity_search_with_score(content1, k=20)
            
            for doc, score in results:
                key2 = doc.metadata.get("key")
                content2 = doc.page_content
                
                # Skip self-comparison and already processed pairs
                if key1 >= key2:  # >= ensures we don't process the same pair twice
                    continue
                
                # Convert distance-like score to similarity
                similarity = 1.0 / (1.0 + float(score))
                
                # Check if above threshold
                if similarity >= threshold:
                    duplicate_pairs.append((key1, key2, content1, content2, similarity))
        
        # Sort by similarity (highest first) and limit results
        duplicate_pairs.sort(key=lambda x: x[4], reverse=True)
        return duplicate_pairs[:max_pairs]
        
    except Exception as e:
        print(f"Error detecting duplicates: {e}")
        return []


# ============================================================================
# Phase 19: Sentiment Analysis (AI Assist)
# ============================================================================

def initialize_sentiment_analysis():
    """Initialize sentiment analysis pipeline."""
    global sentiment_pipeline
    cfg = load_config()
    sentiment_model = cfg.get("sentiment_model", "lxyuan/distilbert-base-multilingual-cased-sentiments-student")
    
    try:
        from transformers import pipeline
        with tqdm(total=100, desc="📥 Sentiment Model", unit="%", ncols=80) as pbar:
            sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=sentiment_model,
                device=-1  # CPU
            )
            pbar.update(100)
        print(f"✅ Sentiment analysis pipeline initialized: {sentiment_model}")
    except Exception as e:
        sentiment_pipeline = None
        print(f"❌ Failed to initialize sentiment analysis: {e}")


def analyze_sentiment_text(content: str) -> dict:
    """
    Analyze sentiment of text content.
    
    Args:
        content: Text to analyze
        
    Returns:
        dict with keys:
        - emotion: Mapped emotion type (joy/sadness/neutral)
        - score: Confidence score (0.0-1.0)
        - raw_label: Original model label (positive/negative/neutral)
    """
    if not sentiment_pipeline:
        return {"emotion": "neutral", "score": 0.0, "raw_label": "unknown", "error": "Pipeline not initialized"}
    
    try:
        # Get prediction
        result = sentiment_pipeline(content[:512])  # Limit to 512 chars for performance
        if not result or len(result) == 0:
            return {"emotion": "neutral", "score": 0.0, "raw_label": "none"}
        
        prediction = result[0]
        raw_label = prediction.get("label", "neutral").lower()
        score = prediction.get("score", 0.0)
        
        # Map to our emotion types
        emotion_map = {
            "positive": "joy",
            "negative": "sadness",
            "neutral": "neutral",
            # Fallbacks
            "pos": "joy",
            "neg": "sadness",
        }
        emotion = emotion_map.get(raw_label, "neutral")
        
        return {
            "emotion": emotion,
            "score": float(score),
            "raw_label": raw_label
        }
        
    except Exception as e:
        print(f"Error analyzing sentiment: {e}")
        return {"emotion": "neutral", "score": 0.0, "raw_label": "error", "error": str(e)}


# ============================================================================
# Phase 23: Migration helpers between SQLite/FAISS and Qdrant
# ============================================================================

def migrate_sqlite_to_qdrant() -> int:
    """Upsert all SQLite memories into Qdrant for current persona.

    Returns: number of records attempted.
    """
    cfg = load_config()
    storage_backend = cfg.get("storage_backend", "sqlite").lower()
    if not QDRANT_AVAILABLE:
        return 0
    # Build/ensure adapter
    try:
        if backend_type == "qdrant" and vector_store is not None:
            adapter = vector_store
        else:
            embeddings_model = cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m")
            embeddings_device = cfg.get("embeddings_device", "cpu")
            emb = HuggingFaceEmbeddings(
                model_name=embeddings_model,
                model_kwargs={'device': embeddings_device},
                encode_kwargs={'normalize_embeddings': True}
            )
            dim = _get_embedding_dimension(embeddings_model)
            url = cfg.get("qdrant_url", "http://localhost:6333")
            api_key = cfg.get("qdrant_api_key")
            prefix = cfg.get("qdrant_collection_prefix", "memory_")
            from persona_utils import get_current_persona
            collection = f"{prefix}{get_current_persona()}"
            client = QdrantClient(url=url, api_key=api_key)
            adapter = QdrantVectorStoreAdapter(client, collection, emb, dim)

        with sqlite3.connect(get_db_path()) as conn:
            cur = conn.cursor()
            cur.execute('SELECT key, content, created_at, updated_at, tags FROM memories')
            rows = cur.fetchall()
        if not rows:
            return 0
        docs = []
        ids = []
        for (k, c, created_at, updated_at, tags_json) in rows:
            meta = {"key": k}
            if created_at:
                meta["created_at"] = created_at
            if updated_at:
                meta["updated_at"] = updated_at
            if tags_json:
                meta["tags"] = tags_json
            docs.append(Document(page_content=c, metadata=meta))
            ids.append(k)
        adapter.add_documents(docs, ids=ids)
        return len(rows)
    except Exception:
        return 0


def migrate_qdrant_to_sqlite(upsert: bool = True) -> int:
    """Pull all points from Qdrant into SQLite memories for the current persona.

    Returns: number of records attempted.
    """
    if not QDRANT_AVAILABLE:
        return 0
    cfg = load_config()
    url = cfg.get("qdrant_url", "http://localhost:6333")
    api_key = cfg.get("qdrant_api_key")
    prefix = cfg.get("qdrant_collection_prefix", "memory_")
    from persona_utils import get_current_persona
    collection = f"{prefix}{get_current_persona()}"
    try:
        client = QdrantClient(url=url, api_key=api_key)
        # Scroll all points
        total = 0
        next_page = None
        with sqlite3.connect(get_db_path()) as conn:
            cur = conn.cursor()
            while True:
                res = client.scroll(collection_name=collection, limit=256, with_payload=True, offset=next_page)
                points, next_page = res[0], res[1]
                if not points:
                    break
                for p in points:
                    pl = p.payload or {}
                    key = pl.get('key')
                    content = pl.get('content')
                    created_at = pl.get('created_at')
                    updated_at = pl.get('updated_at')
                    tags_json = pl.get('tags')
                    if not key or content is None:
                        continue
                    if upsert:
                        cur.execute('''
                            INSERT OR REPLACE INTO memories (key, content, created_at, updated_at, tags)
                            VALUES (?, ?, COALESCE(?, datetime('now')), COALESCE(?, datetime('now')), ?)
                        ''', (key, content, created_at, updated_at, tags_json))
                    else:
                        cur.execute('''
                            INSERT OR IGNORE INTO memories (key, content, created_at, updated_at, tags)
                            VALUES (?, ?, COALESCE(?, datetime('now')), COALESCE(?, datetime('now')), ?)
                        ''', (key, content, created_at, updated_at, tags_json))
                    total += 1
            conn.commit()
        return total
    except Exception:
        return 0
