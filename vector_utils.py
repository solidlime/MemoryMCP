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
try:
    from sentence_transformers import CrossEncoder
    CROSSENCODER_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    CROSSENCODER_AVAILABLE = False

from tqdm import tqdm

from persona_utils import get_db_path, get_vector_store_path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

_config_cache = {}
_config_mtime = 0

def _load_config() -> dict:
    global _config_cache, _config_mtime
    try:
        if os.path.exists(CONFIG_FILE):
            m = os.path.getmtime(CONFIG_FILE)
            if m != _config_mtime or not _config_cache:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    _config_cache = json.load(f)
                _config_mtime = m
        else:
            _config_cache = {}
    except Exception:
        _config_cache = {}
    return _config_cache

def _get_rebuild_config():
    cfg = _load_config() or {}
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

# Idle rebuild controls
_dirty: bool = False
_last_write_ts: float = 0.0
_last_rebuild_ts: float = 0.0
_rebuild_lock = threading.Lock()

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

def initialize_rag_sync():
    """Initialize embeddings/reranker and load or bootstrap a vector store."""
    global vector_store, embeddings, reranker
    cfg = _load_config()
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

    # Vector store load or create
    vs_path = get_vector_store_path()
    legacy_vs_path = os.path.join(SCRIPT_DIR, "vector_store")
    if os.path.exists(legacy_vs_path) and not os.path.exists(vs_path):
        try:
            shutil.copytree(legacy_vs_path, vs_path)
        except Exception:
            pass

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

def save_vector_store():
    if vector_store:
        try:
            vector_store.save_local(get_vector_store_path())
            return True
        except Exception:
            return False
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
        with tqdm(total=1, desc="⚙️  Building FAISS Index", unit="index", ncols=80) as pbar:
            vector_store = FAISS.from_documents(docs, embeddings)
            pbar.update(1)
        save_vector_store()
    except Exception:
        pass

def add_memory_to_vector_store(key: str, content: str):
    mark_vector_store_dirty()

def update_memory_in_vector_store(key: str, content: str):
    mark_vector_store_dirty()

def delete_memory_from_vector_store(key: str):
    mark_vector_store_dirty()

def get_vector_count() -> int:
    try:
        return vector_store.index.ntotal if vector_store else 0
    except Exception:
        return 0
