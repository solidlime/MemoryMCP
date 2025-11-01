import os
import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
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
from qdrant_client import QdrantClient
from lib.backends.qdrant_backend import QdrantVectorStoreAdapter
from persona_utils import get_db_path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _get_rebuild_config():
    cfg = load_config() or {}
    vr = cfg.get("vector_rebuild", {}) if isinstance(cfg, dict) else {}
    return {
        "mode": vr.get("mode", "idle"),
        "idle_seconds": int(vr.get("idle_seconds", 30)),
        "min_interval": int(vr.get("min_interval", 120)),
    }

# Globals for RAG (Phase 25: Qdrant-only)
embeddings = None
reranker = None
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
    """
    Initialize embeddings/reranker.
    Phase 25: Qdrant-only, no global vector_store (per-request adapter pattern)
    """
    global embeddings, reranker
    cfg = load_config()
    embeddings_model = cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m")
    embeddings_device = cfg.get("embeddings_device", "cpu")
    reranker_model = cfg.get("reranker_model", "hotchpotch/japanese-reranker-xsmall-v2")

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
    
    # Phase 19: Initialize sentiment analysis
    initialize_sentiment_analysis()

def rebuild_vector_store():
    """
    Rebuild Qdrant collection from SQLite database.
    Phase 25: Qdrant-only implementation.
    """
    if not embeddings:
        return
    try:
        # Get persona-specific configuration
        cfg = load_config()
        from persona_utils import get_current_persona
        persona = get_current_persona()
        
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        # Create Qdrant adapter
        client = QdrantClient(url=url, api_key=api_key)
        dim = _get_embedding_dimension(cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m"))
        adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        
        # Fetch all memories from SQLite
        with sqlite3.connect(get_db_path()) as conn:
            cur = conn.cursor()
            cur.execute('SELECT key, content, created_at, updated_at, tags, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag FROM memories')
            rows = cur.fetchall()
        
        if not rows:
            return
        
        # Rebuild Qdrant collection with full metadata
        docs = []
        ids = []
        for row in rows:
            key, content, created_at, updated_at, tags_json, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag = row
            meta = {"key": key}
            if created_at:
                meta["created_at"] = created_at
            if updated_at:
                meta["updated_at"] = updated_at
            if tags_json:
                meta["tags"] = tags_json
            if importance is not None:
                meta["importance"] = importance
            if emotion:
                meta["emotion"] = emotion
            if physical_state:
                meta["physical_state"] = physical_state
            if mental_state:
                meta["mental_state"] = mental_state
            if environment:
                meta["environment"] = environment
            if relationship_status:
                meta["relationship_status"] = relationship_status
            if action_tag:
                meta["action_tag"] = action_tag
            
            docs.append(Document(page_content=content, metadata=meta))
            ids.append(key)
        
        with tqdm(total=1, desc="⚙️  Building Qdrant Index", unit="index", ncols=80) as pbar:
            adapter.add_documents(docs, ids=ids)
            pbar.update(1)
        
    except Exception as e:
        print(f"❌ Failed to rebuild vector store: {e}")
        import traceback
        traceback.print_exc()

def add_memory_to_vector_store(key: str, content: str):
    """
    Add a new memory to Qdrant incrementally.
    Phase 24: Dynamic persona-specific adapter pattern.
    Phase 25: Qdrant-only implementation.
    """
    if not embeddings:
        mark_vector_store_dirty()
        return
    
    try:
        # Fetch metadata for richer payload
        created_at = None
        updated_at = None
        tags_json = None
        importance = None
        emotion = None
        physical_state = None
        mental_state = None
        environment = None
        relationship_status = None
        action_tag = None
        try:
            with sqlite3.connect(get_db_path()) as conn:
                cur = conn.cursor()
                cur.execute('SELECT created_at, updated_at, tags, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag FROM memories WHERE key = ?', (key,))
                row = cur.fetchone()
                if row:
                    created_at, updated_at, tags_json, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag = row
        except Exception:
            pass

        meta = {"key": key}
        if created_at:
            meta["created_at"] = created_at
        if updated_at:
            meta["updated_at"] = updated_at
        if tags_json:
            meta["tags"] = tags_json
        if importance is not None:
            meta["importance"] = importance
        if emotion:
            meta["emotion"] = emotion
        if physical_state:
            meta["physical_state"] = physical_state
        if mental_state:
            meta["mental_state"] = mental_state
        if environment:
            meta["environment"] = environment
        if relationship_status:
            meta["relationship_status"] = relationship_status
        if action_tag:
            meta["action_tag"] = action_tag

        # Create document with metadata
        doc = Document(page_content=content, metadata=meta)
        
        # Get current persona and create Qdrant adapter
        cfg = load_config()
        from persona_utils import get_current_persona
        persona = get_current_persona()
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        # Create persona-specific Qdrant vector store
        client = QdrantClient(url=url, api_key=api_key)
        dim = _get_embedding_dimension(cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m"))
        persona_adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        
        # Add to persona-specific Qdrant collection
        persona_adapter.add_documents([doc], ids=[key])
        print(f"✅ Added memory {key} to Qdrant collection {collection}")
            
    except Exception as e:
        print(f"⚠️  Failed to add memory incrementally: {e}, falling back to dirty flag")
        import traceback
        traceback.print_exc()
        mark_vector_store_dirty()

def update_memory_in_vector_store(key: str, content: str):
    """
    Update an existing memory in Qdrant incrementally.
    Phase 25: Qdrant-only implementation.
    """
    if not embeddings:
        mark_vector_store_dirty()
        return
    
    try:
        # Get persona-specific configuration
        cfg = load_config()
        from persona_utils import get_current_persona
        persona = get_current_persona()
        
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        # Create Qdrant adapter
        client = QdrantClient(url=url, api_key=api_key)
        dim = _get_embedding_dimension(cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m"))
        adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        
        # Delete old version
        adapter.delete([key])

        # Fetch metadata (keep original created_at)
        created_at = None
        updated_at = None
        tags_json = None
        importance = None
        emotion = None
        physical_state = None
        mental_state = None
        environment = None
        relationship_status = None
        action_tag = None
        try:
            with sqlite3.connect(get_db_path()) as conn:
                cur = conn.cursor()
                cur.execute('SELECT created_at, updated_at, tags, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag FROM memories WHERE key = ?', (key,))
                row = cur.fetchone()
                if row:
                    created_at, updated_at, tags_json, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag = row
        except Exception:
            pass

        meta = {"key": key}
        if created_at:
            meta["created_at"] = created_at
        if updated_at:
            meta["updated_at"] = updated_at
        if tags_json:
            meta["tags"] = tags_json
        if importance is not None:
            meta["importance"] = importance
        if emotion:
            meta["emotion"] = emotion
        if physical_state:
            meta["physical_state"] = physical_state
        if mental_state:
            meta["mental_state"] = mental_state
        if environment:
            meta["environment"] = environment
        if relationship_status:
            meta["relationship_status"] = relationship_status
        if action_tag:
            meta["action_tag"] = action_tag

        # Add new version
        doc = Document(page_content=content, metadata=meta)
        adapter.add_documents([doc], ids=[key])
        
        print(f"✅ Updated memory {key} in Qdrant collection {collection}")
    except Exception as e:
        print(f"⚠️  Failed to update memory incrementally: {e}, falling back to dirty flag")
        import traceback
        traceback.print_exc()
        mark_vector_store_dirty()

def delete_memory_from_vector_store(key: str):
    """
    Delete a memory from Qdrant incrementally.
    Phase 25: Qdrant-only implementation.
    """
    if not embeddings:
        mark_vector_store_dirty()
        return
    
    try:
        # Get persona-specific configuration
        cfg = load_config()
        from persona_utils import get_current_persona
        persona = get_current_persona()
        
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        # Create Qdrant adapter
        client = QdrantClient(url=url, api_key=api_key)
        dim = _get_embedding_dimension(cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m"))
        adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        
        # Delete from Qdrant
        adapter.delete([key])
        
        print(f"✅ Deleted memory {key} from Qdrant collection {collection}")
    except Exception as e:
        print(f"⚠️  Failed to delete memory incrementally: {e}, falling back to dirty flag")
        import traceback
        traceback.print_exc()
        mark_vector_store_dirty()

def get_vector_count() -> int:
    """Get total vector count from current persona's Qdrant collection"""
    try:
        cfg = load_config()
        from persona_utils import get_current_persona
        persona = get_current_persona()
        
        url = cfg.get("qdrant_url", "http://localhost:6333")
        api_key = cfg.get("qdrant_api_key")
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        client = QdrantClient(url=url, api_key=api_key)
        dim = _get_embedding_dimension(cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m"))
        adapter = QdrantVectorStoreAdapter(client, collection, embeddings, dim)
        
        return adapter.index.ntotal
    except Exception:
        return 0

def get_vector_metrics() -> dict:
    """
    Return detailed metrics for monitoring and debugging.
    Phase 25: Qdrant-only.
    
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
        "backend": "qdrant",  # Phase 25: Always Qdrant
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
