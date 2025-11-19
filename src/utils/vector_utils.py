import os
import json
import os
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

from src.utils.config_utils import load_config
from qdrant_client import QdrantClient
from lib.backends.qdrant_backend import QdrantVectorStoreAdapter
from src.utils.persona_utils import get_db_path, get_current_persona

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _device_str_to_int(device_str: str) -> int:
    """
    Convert device string to transformers pipeline device int.
    
    Args:
        device_str: "cpu", "cuda", "cuda:0", etc.
        
    Returns:
        -1 for CPU, 0+ for GPU index
        
    Examples:
        >>> _device_str_to_int("cpu")
        -1
        >>> _device_str_to_int("cuda")
        0
        >>> _device_str_to_int("cuda:1")
        1
    """
    device_str = device_str.lower().strip()
    if device_str == "cpu":
        return -1
    elif device_str.startswith("cuda"):
        # Extract GPU index if specified (e.g., "cuda:1" -> 1)
        if ":" in device_str:
            try:
                return int(device_str.split(":")[1])
            except (ValueError, IndexError):
                return 0  # Default to GPU 0 on parse error
        return 0  # "cuda" without index -> GPU 0
    return -1  # Unknown device -> default to CPU

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

# Phase 37: Auto-summarization controls
_last_summarization_check: float = 0.0
_summarization_lock = threading.Lock()

def mark_vector_store_dirty():
    global _dirty, _last_write_ts
    _dirty = True
    _last_write_ts = time.time()

def _get_qdrant_adapter(persona: str = None):
    """
    Create a persona-specific Qdrant adapter dynamically.
    Phase 26.5: Centralized adapter creation to avoid code duplication.
    
    Args:
        persona: Persona name (defaults to current persona)
        
    Returns:
        QdrantVectorStoreAdapter instance for the specified persona
    """
    if persona is None:
        persona = get_current_persona()
    
    cfg = load_config()
    url = cfg.get("qdrant_url", "http://localhost:6333")
    api_key = cfg.get("qdrant_api_key")
    prefix = cfg.get("qdrant_collection_prefix", "memory_")
    collection = f"{prefix}{persona}"
    
    client = QdrantClient(url=url, api_key=api_key)
    dim = _get_embedding_dimension(cfg.get("embeddings_model", "cl-nagoya/ruri-v3-30m"))
    
    return QdrantVectorStoreAdapter(client, collection, embeddings, dim)


def _build_enriched_content(
    content: str,
    tags_json: str = None,
    emotion: str = None,
    emotion_intensity: float = None,
    action_tag: str = None,
    environment: str = None,
    physical_state: str = None,
    mental_state: str = None,
    relationship_status: str = None
) -> str:
    """
    Build enriched content for vector embedding by including metadata.
    
    This function adds searchable metadata context to the base content,
    improving semantic search accuracy by making tags, emotions, and other
    contextual information available to the embedding model.
    
    Args:
        content: Base content text
        tags_json: JSON string of tags list
        emotion: Emotion type
        emotion_intensity: Emotion intensity (0.0-1.0)
        action_tag: Action tag
        environment: Environment description
        physical_state: Physical state
        mental_state: Mental state
        relationship_status: Relationship status
        
    Returns:
        Enriched content string with metadata annotations
        
    Example:
        >>> _build_enriched_content(
        ...     "今日はPythonを勉強した。",
        ...     tags_json='["learning", "programming"]',
        ...     emotion="joy",
        ...     emotion_intensity=0.8
        ... )
        '今日はPythonを勉強した。\\n[Tags: learning, programming]\\n[Emotion: joy (intensity: 0.8)]'
    """
    enriched_content = content
    
    # Add tags to searchable content
    if tags_json:
        try:
            tags_list = json.loads(tags_json)
            if tags_list:
                enriched_content += f"\n[Tags: {', '.join(tags_list)}]"
        except:
            pass
    
    # Add emotional context
    if emotion and emotion != "neutral":
        enriched_content += f"\n[Emotion: {emotion}"
        if emotion_intensity and emotion_intensity > 0.5:
            enriched_content += f" (intensity: {emotion_intensity:.1f})"
        enriched_content += "]"
    
    # Add action context
    if action_tag:
        enriched_content += f"\n[Action: {action_tag}]"
    
    # Add environment context
    if environment and environment != "unknown":
        enriched_content += f"\n[Environment: {environment}]"
    
    # Add physical/mental state context
    states = []
    if physical_state and physical_state != "normal":
        states.append(f"physical:{physical_state}")
    if mental_state and mental_state != "calm":
        states.append(f"mental:{mental_state}")
    if states:
        enriched_content += f"\n[State: {', '.join(states)}]"
    
    # Add relationship context
    if relationship_status and relationship_status != "normal":
        enriched_content += f"\n[Relationship: {relationship_status}]"
    
    return enriched_content


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
        "auto_merge_enabled": ac.get("auto_merge_enabled", False),
        "auto_merge_threshold": float(ac.get("auto_merge_threshold", 0.95)),
    }

def _get_summarization_config():
    """Get auto_summarization configuration from config.json"""
    cfg = load_config()
    su = cfg.get("auto_summarization", {})
    return {
        "enabled": su.get("enabled", False),
        "schedule_daily": su.get("schedule_daily", True),
        "schedule_weekly": su.get("schedule_weekly", True),
        "daily_hour": int(su.get("daily_hour", 3)),
        "weekly_day": int(su.get("weekly_day", 0)),  # 0=Monday
        "check_interval_seconds": int(su.get("check_interval_seconds", 3600)),
        "min_importance": float(su.get("min_importance", 0.3)),
    }

def start_cleanup_worker_thread():
    """Start background cleanup worker thread"""
    cfg = _get_cleanup_config()
    if not cfg.get("enabled", True):
        return None
    t = threading.Thread(target=_cleanup_worker_loop, daemon=True)
    t.start()
    return t

def start_summarization_worker_thread():
    """Start background summarization worker thread"""
    cfg = _get_summarization_config()
    if not cfg.get("enabled", False):
        return None
    t = threading.Thread(target=_summarization_worker_loop, daemon=True)
    t.start()
    return t

def _summarization_worker_loop():
    """Background loop that runs periodic summarization"""
    global _last_summarization_check
    
    while True:
        try:
            cfg = _get_summarization_config()
            if not cfg.get("enabled", False):
                time.sleep(60)
                continue
            
            now = time.time()
            check_interval = cfg.get("check_interval_seconds", 3600)
            
            # Wait for check interval
            if (now - _last_summarization_check) < check_interval:
                time.sleep(60)
                continue
            
            # Run summarization check
            with _summarization_lock:
                _last_summarization_check = now
                _run_scheduled_summarization(cfg)
            
            # Sleep after check
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"⚠️ Summarization worker error: {e}")
            time.sleep(60)

def _run_scheduled_summarization(cfg):
    """Run scheduled summarization if due"""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from tools.summarization_tools import summarize_last_day, summarize_last_week
    from src.utils.persona_utils import get_current_persona
    
    try:
        timezone = load_config().get("timezone", "Asia/Tokyo")
        now = datetime.now(ZoneInfo(timezone))
        persona = get_current_persona()
        
        # Check daily summary
        if cfg.get("schedule_daily", True):
            target_hour = cfg.get("daily_hour", 3)
            if now.hour == target_hour:
                print(f"📝 Running daily summary for {persona}...")
                result = summarize_last_day(persona=persona)
                if result:
                    print(f"✅ Daily summary created: {result}")
        
        # Check weekly summary
        if cfg.get("schedule_weekly", True):
            target_day = cfg.get("weekly_day", 0)  # 0=Monday
            if now.weekday() == target_day and now.hour == 3:
                print(f"📝 Running weekly summary for {persona}...")
                result = summarize_last_week(persona=persona)
                if result:
                    print(f"✅ Weekly summary created: {result}")
                    
    except Exception as e:
        print(f"❌ Scheduled summarization error: {e}")
        import traceback
        traceback.print_exc()

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
    """Detect duplicates and save suggestions to file. Auto-merge if enabled."""
    try:
        from src.utils.persona_utils import get_current_persona, get_persona_dir
        
        persona = get_current_persona()
        threshold = cfg.get("duplicate_threshold", 0.90)
        max_pairs = cfg.get("max_suggestions_per_run", 20)
        auto_merge_enabled = cfg.get("auto_merge_enabled", False)
        auto_merge_threshold = cfg.get("auto_merge_threshold", 0.95)
        
        print(f"🧹 Running cleanup check for persona: {persona} (threshold: {threshold:.2f})...")
        
        # Detect duplicates
        duplicates = detect_duplicate_memories(threshold, max_pairs)
        
        if not duplicates:
            print(f"✅ No cleanup suggestions (threshold: {threshold:.2f})")
            return
        
        # Auto-merge if enabled
        merged_count = 0
        if auto_merge_enabled:
            print(f"🔗 Auto-merge enabled (threshold: {auto_merge_threshold:.2f})")
            merged_count = _auto_merge_duplicates(duplicates, auto_merge_threshold)
            if merged_count > 0:
                print(f"✅ Auto-merged {merged_count} duplicate pairs")
                # Re-detect after merging
                duplicates = detect_duplicate_memories(threshold, max_pairs)
        
        # Group remaining duplicates into suggestion groups
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
            "auto_merged": merged_count,
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
        if merged_count > 0:
            print(f"   🔗 Auto-merged: {merged_count} pairs")
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
        from src.utils.persona_utils import get_db_path
        import sqlite3
        
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            return cursor.fetchone()[0]
    except Exception:
        return 0


def _auto_merge_duplicates(duplicates: list, threshold: float) -> int:
    """Auto-merge duplicate pairs above threshold.
    
    Args:
        duplicates: List of tuples [(key1, key2, content1, content2, similarity), ...]
        threshold: Minimum similarity to auto-merge (0.0-1.0)
        
    Returns:
        Number of pairs merged
    """
    from core.memory_db import load_memory_from_db, save_memory_to_db, delete_memory_from_db, generate_auto_key
    from datetime import datetime
    
    merged_count = 0
    
    for key1, key2, content1, content2, similarity in duplicates:
        if similarity < threshold:
            continue
        
        try:
            # Load both memories
            memory1 = load_memory_from_db(key1)
            memory2 = load_memory_from_db(key2)
            
            if not memory1 or not memory2:
                continue
            
            # Merge contents (concatenate with separator)
            merged_content = f"{content1}\n\n{content2}"
            
            # Merge tags
            tags1 = set(memory1.get("tags", []))
            tags2 = set(memory2.get("tags", []))
            merged_tags = list(tags1.union(tags2))
            
            # Use earliest created_at
            created1 = datetime.fromisoformat(memory1["created_at"])
            created2 = datetime.fromisoformat(memory2["created_at"])
            earliest = min(created1, created2)
            
            # Use higher importance
            importance1 = memory1.get("importance", 0.5)
            importance2 = memory2.get("importance", 0.5)
            merged_importance = max(importance1, importance2)
            
            # Use stronger emotion
            emotion1 = memory1.get("emotion", "neutral")
            emotion2 = memory2.get("emotion", "neutral")
            intensity1 = memory1.get("emotion_intensity", 0.5)
            intensity2 = memory2.get("emotion_intensity", 0.5)
            
            if intensity1 >= intensity2:
                merged_emotion = emotion1
                merged_intensity = intensity1
            else:
                merged_emotion = emotion2
                merged_intensity = intensity2
            
            # Generate new key
            new_key = generate_auto_key()
            
            # Save merged memory
            save_memory_to_db(
                key=new_key,
                content=merged_content,
                tags=merged_tags,
                importance=merged_importance,
                emotion=merged_emotion,
                emotion_intensity=merged_intensity,
                physical_state=memory1.get("physical_state"),
                mental_state=memory1.get("mental_state"),
                environment=memory1.get("environment"),
                relationship_status=memory1.get("relationship_status"),
                action_tag=memory1.get("action_tag"),
                related_keys=None,
                summary_ref=None
            )
            
            # Delete originals
            delete_memory_from_db(key1)
            delete_memory_from_db(key2)
            
            merged_count += 1
            print(f"   ✅ Merged {key1} + {key2} → {new_key} (similarity: {similarity:.3f})")
            
        except Exception as e:
            print(f"   ⚠️  Failed to merge {key1} + {key2}: {e}")
            continue
    
    return merged_count

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
    rag_device = cfg.get("embeddings_device", "cpu")  # Unified device for all RAG models
    reranker_model = cfg.get("reranker_model", "hotchpotch/japanese-reranker-xsmall-v2")

    # Disable torch compile to avoid ModernBERT issues
    import os
    os.environ["TORCH_COMPILE_DISABLE"] = "1"
    
    # Force CPU mode if specified (helps avoid CUDA auto-selection)
    if rag_device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    
    # Suppress transformers warnings
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    # Embeddings
    try:
        with tqdm(total=100, desc="📥 Embeddings Model", unit="%", ncols=80) as pbar:
            embeddings = HuggingFaceEmbeddings(
                model_name=embeddings_model,
                model_kwargs={'device': rag_device},
                encode_kwargs={'normalize_embeddings': True}
            )
            pbar.update(100)
    except Exception as e:
        print(f"❌ Failed to initialize embeddings: {e}")
        import traceback
        traceback.print_exc()
        embeddings = None

    # Reranker
    if CROSSENCODER_AVAILABLE:
        try:
            with tqdm(total=100, desc="📥 Reranker Model", unit="%", ncols=80) as pbar:
                # Use unified RAG device setting
                reranker = CrossEncoder(reranker_model, device=rag_device)
                pbar.update(100)
        except Exception as e:
            print(f"❌ Failed to initialize reranker: {e}")
            import traceback
            traceback.print_exc()
            reranker = None
    else:
        reranker = None
    
    # Phase 19: Initialize sentiment analysis with unified device
    initialize_sentiment_analysis(device=rag_device)

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
        from src.utils.persona_utils import get_current_persona
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
            # Check if importance column exists (backward compatibility)
            cur.execute("PRAGMA table_info(memories)")
            columns = [col[1] for col in cur.fetchall()]
            has_importance = 'importance' in columns
            has_equipped_items = 'equipped_items' in columns
            
            if has_importance and has_equipped_items:
                cur.execute('SELECT key, content, created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref, equipped_items FROM memories')
            elif has_importance:
                cur.execute('SELECT key, content, created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref FROM memories')
            else:
                # Old schema without importance
                cur.execute('SELECT key, content, created_at, updated_at, tags FROM memories')
            rows = cur.fetchall()
        
        if not rows:
            return
        
        # Rebuild Qdrant collection with full metadata
        docs = []
        ids = []
        for row in rows:
            # Handle different schema versions
            if has_importance and has_equipped_items:
                key, content, created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref, equipped_items_json = row
            elif has_importance:
                key, content, created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref = row
                equipped_items_json = None
            else:
                # Old schema: only key, content, created_at, updated_at, tags
                key, content, created_at, updated_at, tags_json = row
                importance = 0.5
                emotion = 'neutral'
                emotion_intensity = 0.5
                physical_state = mental_state = environment = relationship_status = action_tag = None
                related_keys_json = summary_ref = equipped_items_json = None
            
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
            if emotion_intensity is not None:
                meta["emotion_intensity"] = emotion_intensity
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
            if related_keys_json:
                meta["related_keys"] = related_keys_json
            if summary_ref:
                meta["summary_ref"] = summary_ref
            if equipped_items_json:
                meta["equipped_items"] = equipped_items_json
            
            # Build enriched content for vector embedding
            enriched_content = _build_enriched_content(
                content=content,
                tags_json=tags_json,
                emotion=emotion,
                emotion_intensity=emotion_intensity,
                action_tag=action_tag,
                environment=environment,
                physical_state=physical_state,
                mental_state=mental_state,
                relationship_status=relationship_status
            )
            
            docs.append(Document(page_content=enriched_content, metadata=meta))
            ids.append(key)
        
        # Batch upload with progress bar
        batch_size = 50
        total_docs = len(docs)
        
        with tqdm(total=total_docs, desc="⚙️  Building Qdrant Index", unit="memory", ncols=80) as pbar:
            for i in range(0, total_docs, batch_size):
                batch_docs = docs[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                adapter.add_documents(batch_docs, ids=batch_ids)
                pbar.update(len(batch_docs))
        
        print(f"✅ Rebuilt vector store: {total_docs} memories indexed in collection '{collection}'")
        
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
        emotion_intensity = None
        physical_state = None
        mental_state = None
        environment = None
        relationship_status = None
        action_tag = None
        related_keys_json = None
        summary_ref = None
        equipped_items_json = None
        try:
            with sqlite3.connect(get_db_path()) as conn:
                cur = conn.cursor()
                cur.execute('SELECT created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref, equipped_items FROM memories WHERE key = ?', (key,))
                row = cur.fetchone()
                if row:
                    created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref, equipped_items_json = row
        except Exception:
            pass

        meta = {"key": key}
        if created_at:
            meta["created_at"] = created_at
            # Add searchable datetime context
            from core.time_utils import get_datetime_context
            created_ctx = get_datetime_context(created_at)
            meta["created_weekday"] = created_ctx["weekday_en"]
            meta["created_weekday_ja"] = created_ctx["weekday_ja"]
            meta["created_month"] = created_ctx["month"]
            meta["created_year"] = created_ctx["year"]
            meta["created_display"] = created_ctx["display"]
        if updated_at:
            meta["updated_at"] = updated_at
            # Add searchable datetime context
            from core.time_utils import get_datetime_context
            updated_ctx = get_datetime_context(updated_at)
            meta["updated_weekday"] = updated_ctx["weekday_en"]
            meta["updated_weekday_ja"] = updated_ctx["weekday_ja"]
            meta["updated_month"] = updated_ctx["month"]
            meta["updated_year"] = updated_ctx["year"]
            meta["updated_display"] = updated_ctx["display"]
        if tags_json:
            meta["tags"] = tags_json
        if importance is not None:
            meta["importance"] = importance
        if emotion:
            meta["emotion"] = emotion
        if emotion_intensity is not None:
            meta["emotion_intensity"] = emotion_intensity
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
        if related_keys_json:
            meta["related_keys"] = related_keys_json
        if summary_ref:
            meta["summary_ref"] = summary_ref
        if equipped_items_json:
            meta["equipped_items"] = equipped_items_json

        # Build enriched content for vector embedding
        enriched_content = _build_enriched_content(
            content=content,
            tags_json=tags_json,
            emotion=emotion,
            emotion_intensity=emotion_intensity,
            action_tag=action_tag,
            environment=environment,
            physical_state=physical_state,
            mental_state=mental_state,
            relationship_status=relationship_status
        )

        # Create document with enriched content and metadata
        doc = Document(page_content=enriched_content, metadata=meta)
        
        # Phase 26.5: Use centralized adapter creation
        persona = get_current_persona()
        adapter = _get_qdrant_adapter(persona)
        
        # Add to persona-specific Qdrant collection
        cfg = load_config()
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        adapter.add_documents([doc], ids=[key])
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
    Phase 26.5: Use centralized adapter creation.
    """
    if not embeddings:
        mark_vector_store_dirty()
        return
    
    try:
        # Phase 26.5: Use centralized adapter creation
        persona = get_current_persona()
        adapter = _get_qdrant_adapter(persona)
        
        # Get collection name
        cfg = load_config()
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
        # Delete old version
        adapter.delete([key])

        # Fetch metadata (keep original created_at)
        created_at = None
        updated_at = None
        tags_json = None
        importance = None
        emotion = None
        emotion_intensity = None
        physical_state = None
        mental_state = None
        environment = None
        relationship_status = None
        action_tag = None
        related_keys_json = None
        summary_ref = None
        equipped_items_json = None
        try:
            with sqlite3.connect(get_db_path()) as conn:
                cur = conn.cursor()
                cur.execute('SELECT created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref, equipped_items FROM memories WHERE key = ?', (key,))
                row = cur.fetchone()
                if row:
                    created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref, equipped_items_json = row
        except Exception:
            pass

        meta = {"key": key}
        if created_at:
            meta["created_at"] = created_at
            # Add searchable datetime context
            from core.time_utils import get_datetime_context
            created_ctx = get_datetime_context(created_at)
            meta["created_weekday"] = created_ctx["weekday_en"]
            meta["created_weekday_ja"] = created_ctx["weekday_ja"]
            meta["created_month"] = created_ctx["month"]
            meta["created_year"] = created_ctx["year"]
            meta["created_display"] = created_ctx["display"]
        if updated_at:
            meta["updated_at"] = updated_at
            # Add searchable datetime context
            from core.time_utils import get_datetime_context
            updated_ctx = get_datetime_context(updated_at)
            meta["updated_weekday"] = updated_ctx["weekday_en"]
            meta["updated_weekday_ja"] = updated_ctx["weekday_ja"]
            meta["updated_month"] = updated_ctx["month"]
            meta["updated_year"] = updated_ctx["year"]
            meta["updated_display"] = updated_ctx["display"]
        if tags_json:
            meta["tags"] = tags_json
        if importance is not None:
            meta["importance"] = importance
        if emotion:
            meta["emotion"] = emotion
        if emotion_intensity is not None:
            meta["emotion_intensity"] = emotion_intensity
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
        if related_keys_json:
            meta["related_keys"] = related_keys_json
        if summary_ref:
            meta["summary_ref"] = summary_ref

        # Build enriched content for vector embedding
        enriched_content = _build_enriched_content(
            content=content,
            tags_json=tags_json,
            emotion=emotion,
            emotion_intensity=emotion_intensity,
            action_tag=action_tag,
            environment=environment,
            physical_state=physical_state,
            mental_state=mental_state,
            relationship_status=relationship_status
        )

        # Add new version with enriched content
        doc = Document(page_content=enriched_content, metadata=meta)
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
    Phase 26.5: Use centralized adapter creation.
    """
    if not embeddings:
        mark_vector_store_dirty()
        return
    
    try:
        # Phase 26.5: Use centralized adapter creation
        persona = get_current_persona()
        adapter = _get_qdrant_adapter(persona)
        
        # Get collection name
        cfg = load_config()
        prefix = cfg.get("qdrant_collection_prefix", "memory_")
        collection = f"{prefix}{persona}"
        
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
        from src.utils.persona_utils import get_current_persona
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
    try:
        # Phase 26.5: Use dynamic adapter instead of global vector_store
        persona = get_current_persona()
        adapter = _get_qdrant_adapter(persona)
        
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
        results = adapter.similarity_search_with_score(query_content, k=top_k + 1)
        
        # Filter out the query memory itself and format results
        similar = []
        for doc, score in results:
            key = doc.metadata.get("key")
            if key != query_key:  # Exclude the query memory itself
                # Phase 31.2: score is now similarity directly (higher = more similar)
                similarity = float(score)
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
    try:
        # Phase 26.5: Use dynamic adapter instead of global vector_store
        persona = get_current_persona()
        adapter = _get_qdrant_adapter(persona)
        
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
        with tqdm(total=len(all_memories), desc="🔍 Detecting Duplicates", unit="memory", ncols=80) as pbar:
            for i in range(len(all_memories)):
                key1, content1 = all_memories[i]
                
                # Search for similar memories
                results = adapter.similarity_search_with_score(content1, k=20)
                
                for doc, score in results:
                    key2 = doc.metadata.get("key")
                    content2 = doc.page_content
                    
                    # Skip self-comparison and already processed pairs
                    if key1 >= key2:  # >= ensures we don't process the same pair twice
                        continue
                    
                    # Phase 31.2: score is now similarity directly (higher = more similar)
                    similarity = float(score)
                    
                    # Check if above threshold
                    if similarity >= threshold:
                        duplicate_pairs.append((key1, key2, content1, content2, similarity))
                
                pbar.update(1)
        
        # Sort by similarity (highest first) and limit results
        duplicate_pairs.sort(key=lambda x: x[4], reverse=True)
        return duplicate_pairs[:max_pairs]
        
    except Exception as e:
        print(f"Error detecting duplicates: {e}")
        return []


# ============================================================================
# Phase 19: Sentiment Analysis (AI Assist)
# ============================================================================

def initialize_sentiment_analysis(device: str = "cpu"):
    """
    Initialize sentiment analysis pipeline.
    
    Args:
        device: Device string ("cpu", "cuda", "cuda:0", etc.)
    """
    global sentiment_pipeline
    
    cfg = load_config()
    sentiment_model = cfg.get("sentiment_model", "lxyuan/distilbert-base-multilingual-cased-sentiments-student")
    
    # Convert device string to transformers pipeline device format
    device_int = _device_str_to_int(device)
    
    try:
        from transformers import pipeline
        with tqdm(total=100, desc="📥 Sentiment Model", unit="%", ncols=80) as pbar:
            sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=sentiment_model,
                device=device_int
            )
            pbar.update(100)
        print(f"✅ Sentiment analysis pipeline initialized: {sentiment_model}")
    except Exception as e:
        sentiment_pipeline = None
        print(f"❌ Failed to initialize sentiment analysis: {e}")
        import traceback
        traceback.print_exc()


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
