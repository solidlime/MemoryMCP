import asyncio
import json
import os
import sys
import uuid
import shutil
import sqlite3
import warnings
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from mcp.server.fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

# Suppress websockets legacy deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='websockets.legacy')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='uvicorn.protocols.websockets')
# Suppress FAISS SWIG deprecation warnings
warnings.filterwarnings('ignore', message='builtin type.*has no __module__ attribute')

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
DEFAULT_CONFIG = {
    "embeddings_model": "cl-nagoya/ruri-v3-30m",
    "embeddings_device": "cpu",
    "reranker_model": "hotchpotch/japanese-reranker-xsmall-v2",
    "reranker_top_n": 5,
    "server_host": "127.0.0.1",
    "server_port": 8000
}

# Global config storage
_config = {}
_config_mtime = 0

def load_config() -> dict:
    """Load configuration from config.json with hot reload support"""
    global _config, _config_mtime
    
    try:
        # Check if config file exists and has been modified
        if os.path.exists(CONFIG_FILE):
            current_mtime = os.path.getmtime(CONFIG_FILE)
            
            # Reload if file was modified or not loaded yet
            if current_mtime != _config_mtime or not _config:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    _config = {**DEFAULT_CONFIG, **json.load(f)}
                _config_mtime = current_mtime
                _log_progress(f"✅ Config loaded/reloaded from {CONFIG_FILE}")
        else:
            # Create default config file if it doesn't exist
            _config = DEFAULT_CONFIG.copy()
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            _config_mtime = os.path.getmtime(CONFIG_FILE)
            _log_progress(f"✅ Created default config at {CONFIG_FILE}")
    except Exception as e:
        _log_progress(f"⚠️  Failed to load config, using defaults: {e}")
        _config = DEFAULT_CONFIG.copy()
    
    return _config

def get_config(key: str, default=None):
    """Get configuration value with hot reload check"""
    config = load_config()
    return config.get(key, default)

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    import io
    try:
        # Try to reconfigure stdout/stderr for emoji support
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
            sys.stderr.reconfigure(encoding='utf-8')  # type: ignore
    except (AttributeError, OSError):
        # Fallback for older Python versions or when reconfigure fails
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except (AttributeError, OSError):
            # If all else fails, just continue with default encoding
            pass

# LangChain & RAG imports
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

# Phase 16: Fuzzy search support
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    fuzz = None
    process = None
    RAPIDFUZZ_AVAILABLE = False

# Load configuration early for server settings
_early_config = {}
try:
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), 'r', encoding='utf-8') as f:
            _early_config = json.load(f)
except:
    pass

# Initialize MCP server with configured host and port
mcp = FastMCP(
    "Memory Service",
    host=_early_config.get("server_host", "127.0.0.1"),
    port=_early_config.get("server_port", 8000)
)

# Persona context variable (thread-safe, request-scoped)
current_persona: ContextVar[str] = ContextVar('current_persona', default='default')

def get_current_persona() -> str:
    """Get current persona from HTTP request header or context variable"""
    try:
        # Try to get request from FastMCP dependencies
        request = get_http_request()
        if request:
            # Get X-Persona header (headers are case-insensitive in Starlette)
            persona = request.headers.get('x-persona', 'default')
            _log_progress(f"🔄 Request received - Persona from header: {persona}")
            return persona
    except Exception as e:
        # Fallback to context variable if request is not available
        _log_progress(f"⚠️  Could not get request, using context: {e}")
        pass
    
    # Return context variable value
    return current_persona.get()

LOG_FILE = os.path.join(SCRIPT_DIR, "memory_operations.log")

memory_store = {}
vector_store = None
embeddings = None
reranker = None

def _log_progress(message: str):
    """Log progress message to file (avoiding MCP protocol interference)"""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] PROGRESS: {message}\n")
    except Exception:
        pass  # Silently fail if logging fails

def get_persona_dir(persona: str = None) -> str:
    """Get persona-specific directory path"""
    if persona is None:
        persona = get_current_persona()
    # Sanitize persona name (remove path separators)
    safe_persona = persona.replace('/', '_').replace('\\', '_')
    persona_dir = os.path.join(SCRIPT_DIR, "memory", safe_persona)
    os.makedirs(persona_dir, exist_ok=True)
    return persona_dir

def get_db_path(persona: str = None) -> str:
    """Get persona-specific SQLite database path with legacy migration"""
    if persona is None:
        persona = get_current_persona()
    
    persona_dir = get_persona_dir(persona)
    new_db_path = os.path.join(persona_dir, "memory.sqlite")
    
    # Check for legacy database (memory/{persona}.sqlite)
    safe_persona = persona.replace('/', '_').replace('\\', '_')
    legacy_db_path = os.path.join(SCRIPT_DIR, "memory", f"{safe_persona}.sqlite")
    
    # Migrate legacy database if exists
    if os.path.exists(legacy_db_path) and not os.path.exists(new_db_path):
        _log_progress(f"🔄 Migrating legacy database: {legacy_db_path} -> {new_db_path}")
        try:
            os.replace(legacy_db_path, new_db_path)
            _log_progress(f"✅ Migrated legacy database to {new_db_path}")
        except Exception as e:
            _log_progress(f"❌ Failed to migrate legacy database: {e}")
    
    return new_db_path

def get_vector_store_path(persona: str = None) -> str:
    """Get persona-specific vector store path"""
    if persona is None:
        persona = get_current_persona()
    persona_dir = get_persona_dir(persona)
    return os.path.join(persona_dir, "vector_store")

def get_persona_context_path(persona: str = None) -> str:
    """Get persona-specific context JSON file path"""
    if persona is None:
        persona = get_current_persona()
    persona_dir = get_persona_dir(persona)
    return os.path.join(persona_dir, "persona_context.json")

# ========================================
# Phase 12: Time-awareness Functions
# ========================================

def get_current_time() -> datetime:
    """
    Get current time in configured timezone.
    Returns timezone-aware datetime object.
    """
    config = load_config()
    timezone_str = config.get("timezone", "Asia/Tokyo")
    try:
        tz = ZoneInfo(timezone_str)
        return datetime.now(tz)
    except Exception as e:
        _log_progress(f"⚠️  Invalid timezone '{timezone_str}', using UTC: {e}")
        return datetime.now(ZoneInfo("UTC"))

def parse_date_query(date_query: str) -> tuple:
    """
    Parse date query string into start and end datetime objects.
    
    Args:
        date_query: Date query string (e.g., "今日", "昨日", "2025-10-01", "2025-10-01..2025-10-31")
    
    Returns:
        tuple: (start_date, end_date) as timezone-aware datetime objects
    
    Raises:
        ValueError: If date format is invalid
    """
    import re
    current_time = get_current_time()
    start_date = None
    end_date = None
    
    # Handle relative date expressions
    if date_query in ["今日", "today"]:
        start_date = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif date_query in ["昨日", "yesterday"]:
        yesterday = current_time - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif date_query in ["今週", "this week"]:
        # Start of week (Monday)
        start_date = current_time - timedelta(days=current_time.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = current_time
    elif date_query in ["先週", "last week"]:
        # Last week Monday to Sunday
        start_date = current_time - timedelta(days=current_time.weekday() + 7)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
    elif date_query in ["今月", "this month"]:
        start_date = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = current_time
    elif "日前" in date_query or "days ago" in date_query:
        # Extract number of days
        match = re.search(r'(\d+)', date_query)
        if match:
            days = int(match.group(1))
            target_date = current_time - timedelta(days=days)
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            raise ValueError(f"Could not parse days from: '{date_query}'")
    elif ".." in date_query:
        # Date range: "YYYY-MM-DD..YYYY-MM-DD"
        parts = date_query.split("..")
        if len(parts) == 2:
            start_date = datetime.fromisoformat(parts[0])
            end_date = datetime.fromisoformat(parts[1])
            # Make timezone-aware
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=current_time.tzinfo)
            if end_date.tzinfo is None:
                end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=current_time.tzinfo)
        else:
            raise ValueError(f"Invalid date range format: '{date_query}' (expected YYYY-MM-DD..YYYY-MM-DD)")
    else:
        # Specific date: "YYYY-MM-DD"
        try:
            target_date = datetime.fromisoformat(date_query)
            if target_date.tzinfo is None:
                target_date = target_date.replace(tzinfo=current_time.tzinfo)
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            raise ValueError(f"Invalid date format: '{date_query}'. Use 'YYYY-MM-DD', '今日', '昨日', '3日前', or 'YYYY-MM-DD..YYYY-MM-DD'")
    
    if start_date is None or end_date is None:
        raise ValueError(f"Could not parse date query: '{date_query}'")
    
    return (start_date, end_date)

def calculate_time_diff(start_time: str, end_time: str = None) -> dict:
    """
    Calculate time difference between two timestamps.
    
    Args:
        start_time: ISO format timestamp string
        end_time: ISO format timestamp string (defaults to current time)
    
    Returns:
        dict with keys: days, hours, minutes, total_hours, formatted_string
    """
    try:
        # Parse start time
        if isinstance(start_time, str):
            start_dt = datetime.fromisoformat(start_time)
        else:
            start_dt = start_time
        
        # Make start_dt timezone-aware if it's naive
        if start_dt.tzinfo is None:
            config = load_config()
            timezone_str = config.get("timezone", "Asia/Tokyo")
            tz = ZoneInfo(timezone_str)
            start_dt = start_dt.replace(tzinfo=tz)
        
        # Get end time (current time if not specified)
        if end_time is None:
            end_dt = get_current_time()
        elif isinstance(end_time, str):
            end_dt = datetime.fromisoformat(end_time)
            # Make end_dt timezone-aware if it's naive
            if end_dt.tzinfo is None:
                config = load_config()
                timezone_str = config.get("timezone", "Asia/Tokyo")
                tz = ZoneInfo(timezone_str)
                end_dt = end_dt.replace(tzinfo=tz)
        else:
            end_dt = end_time
        
        # Calculate difference
        delta = end_dt - start_dt
        
        total_seconds = delta.total_seconds()
        days = delta.days
        hours = int((total_seconds % 86400) / 3600)
        minutes = int((total_seconds % 3600) / 60)
        total_hours = total_seconds / 3600
        
        # Format string
        parts = []
        if days > 0:
            parts.append(f"{days}日")
        if hours > 0:
            parts.append(f"{hours}時間")
        if minutes > 0:
            parts.append(f"{minutes}分")
        
        formatted = " ".join(parts) if parts else "1分未満"
        
        return {
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "total_hours": total_hours,
            "formatted_string": formatted
        }
    except Exception as e:
        _log_progress(f"❌ Failed to calculate time diff: {e}")
        return {
            "days": 0,
            "hours": 0,
            "minutes": 0,
            "total_hours": 0,
            "formatted_string": "計算エラー"
        }

def load_persona_context(persona: str = None) -> dict:
    """
    Load persona context from JSON file.
    
    Returns:
        dict with persona context data
    """
    if persona is None:
        persona = get_current_persona()
    
    context_path = get_persona_context_path(persona)
    
    # Default context structure
    default_context = {
        "user_info": {
            "name": "User",
            "nickname": None,
            "preferred_address": None
        },
        "persona_info": {
            "name": persona,
            "nickname": None,
            "preferred_address": None
        },
        "last_conversation_time": None,
        "current_emotion": "neutral",
        "physical_state": "normal",
        "mental_state": "calm",
        "environment": "unknown",
        "relationship_status": "normal"
    }
    
    try:
        if os.path.exists(context_path):
            with open(context_path, 'r', encoding='utf-8') as f:
                context = json.load(f)
                _log_progress(f"✅ Loaded persona context from {context_path}")
                return context
        else:
            # Create default context file
            save_persona_context(default_context, persona)
            _log_progress(f"✅ Created default persona context at {context_path}")
            return default_context
    except Exception as e:
        _log_progress(f"❌ Failed to load persona context: {e}")
        return default_context

def save_persona_context(context: dict, persona: str = None) -> bool:
    """
    Save persona context to JSON file.
    
    Args:
        context: dict with persona context data
        persona: persona name (defaults to current persona)
    
    Returns:
        bool indicating success
    """
    if persona is None:
        persona = get_current_persona()
    
    context_path = get_persona_context_path(persona)
    
    try:
        # Create backup if file exists
        if os.path.exists(context_path):
            backup_path = f"{context_path}.backup"
            shutil.copy2(context_path, backup_path)
        
        # Save context
        with open(context_path, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=2, ensure_ascii=False)
        
        _log_progress(f"✅ Saved persona context to {context_path}")
        return True
    except Exception as e:
        _log_progress(f"❌ Failed to save persona context: {e}")
        return False

# ========================================
# End of Phase 12 Time-awareness Functions
# ========================================

def _initialize_rag_sync():
    """Initialize RAG components (called from background thread)"""
    global vector_store, embeddings, reranker
    
    try:
        # Load configuration
        config = load_config()
        embeddings_model = config.get("embeddings_model", "cl-nagoya/ruri-v3-30m")
        embeddings_device = config.get("embeddings_device", "cpu")
        reranker_model = config.get("reranker_model", "hotchpotch/japanese-reranker-xsmall-v2")
        reranker_top_n = config.get("reranker_top_n", 5)
        
        # Initialize embeddings model (multilingual model for better Japanese support)
        print(f"📥 Loading embeddings model: {embeddings_model}...")
        _log_progress(f"📥 Loading embeddings model: {embeddings_model}...")
        
        try:
            # Use tqdm to show download progress for embeddings model
            with tqdm(total=100, desc="📥 Embeddings Model", unit="%", ncols=80) as pbar:
                embeddings = HuggingFaceEmbeddings(
                    model_name=embeddings_model,
                    model_kwargs={'device': embeddings_device},
                    encode_kwargs={'normalize_embeddings': True}
                )
                pbar.update(100)
            
            print("✅ Embeddings model loaded successfully!")
            _log_progress("✅ Embeddings model loaded successfully!")
        except Exception as e:
            print(f"❌ Failed to load embeddings model: {e}")
            _log_progress(f"❌ Failed to load embeddings model: {e}")
            print("⚠️  Embeddings disabled - vector search will not be available")
            _log_progress("⚠️  Embeddings disabled - vector search will not be available")
            embeddings = None
        
        # Initialize reranker model (using lightweight Japanese model)
        print(f"📥 Loading reranker model: {reranker_model}...")
        _log_progress(f"📥 Loading reranker model: {reranker_model}...")
        
        # Check if reranker library is available
        if not CROSSENCODER_AVAILABLE:
            print("⚠️  Reranker library not available (sentence-transformers.CrossEncoder)")
            _log_progress("⚠️  Reranker library not available")
            print("✅ Reranker disabled - falling back to basic similarity search")
            _log_progress("✅ Reranker disabled - falling back to basic similarity search")
            reranker = None
        else:
            try:
                # Use tqdm to show download progress for reranker model
                with tqdm(total=100, desc="📥 Reranker Model", unit="%", ncols=80) as pbar:
                    reranker = CrossEncoder(reranker_model)
                    pbar.update(100)
                
                print("✅ Reranker model loaded successfully!")
                _log_progress("✅ Reranker model loaded successfully!")
            except Exception as e:
                print(f"❌ Failed to load reranker model: {e}")
                _log_progress(f"❌ Failed to load reranker model: {e}")
                print("✅ Reranker disabled - falling back to basic similarity search")
                _log_progress("✅ Reranker disabled - falling back to basic similarity search")
                reranker = None  # Fallback to no reranking
        
        # Load existing vector store if it exists (persona-scoped)
        print("📁 Checking for existing vector store (persona-scoped)...")
        _log_progress("📁 Checking for existing vector store (persona-scoped)...")
        
        vector_store_path = get_vector_store_path()
        
        # Check for legacy vector store and migrate
        legacy_vector_store_path = os.path.join(SCRIPT_DIR, "vector_store")
        if os.path.exists(legacy_vector_store_path) and not os.path.exists(vector_store_path):
            _log_progress(f"🔄 Migrating legacy vector store: {legacy_vector_store_path} -> {vector_store_path}")
            try:
                shutil.copytree(legacy_vector_store_path, vector_store_path)
                _log_progress(f"✅ Migrated legacy vector store to {vector_store_path}")
            except Exception as e:
                _log_progress(f"❌ Failed to migrate legacy vector store: {e}")
        
        if os.path.exists(vector_store_path) and embeddings is not None:
            try:
                print("📥 Loading vector store from disk (persona)...")
                _log_progress("📥 Loading vector store from disk (persona)...")
                vector_store = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
                print(f"✅ Loaded existing vector store with {vector_store.index.ntotal} documents.")
                _log_progress(f"✅ Loaded existing vector store with {vector_store.index.ntotal} documents.")
                
                # Check if vector store needs rebuilding (comparing count)
                if len(memory_store) > 0 and vector_store.index.ntotal != len(memory_store):
                    print(f"⚠️  Vector store count ({vector_store.index.ntotal}) != memory count ({len(memory_store)}). Rebuilding...")
                    _log_progress(f"⚠️  Vector store count ({vector_store.index.ntotal}) != memory count ({len(memory_store)}). Rebuilding...")
                    rebuild_vector_store()
            except Exception as e:
                print(f"❌ Failed to load vector store: {e}")
                _log_progress(f"❌ Failed to load vector store: {e}")
                vector_store = None
        
        if vector_store is None and embeddings is not None:
            # Rebuild vector store from all existing memories
            if memory_store:
                print("🔨 No vector store found. Building from existing memories...")
                _log_progress("🔨 No vector store found. Building from existing memories...")
                rebuild_vector_store()
            else:
                # Create empty vector store with a dummy document
                print("🆕 Creating new empty vector store...")
                _log_progress("🆕 Creating new empty vector store...")
                dummy_doc = Document(page_content="初期化用ダミー", metadata={"key": "dummy"})
                vector_store = FAISS.from_documents([dummy_doc], embeddings)
                print("✅ Created new vector store with dummy document.")
                _log_progress("✅ Created new vector store with dummy document.")
        
        # Mark initialization as complete
        print("🎉 RAG system is ready!")
        _log_progress("🎉 RAG system is ready!")
        
    except Exception as e:
        print(f"❌ RAG initialization failed: {e}")
        _log_progress(f"❌ RAG initialization failed: {e}")


def save_vector_store():
    """Save vector store to disk (persona-scoped)"""
    if vector_store:
        try:
            vector_store_path = get_vector_store_path()
            vector_store.save_local(vector_store_path)
            return True
        except Exception as e:
            print(f"Failed to save vector store: {e}")
            return False
    return False

def add_memory_to_vector_store(key: str, content: str):
    """Add memory to vector store"""
    global vector_store
    if vector_store is None:
        return
    
    if vector_store and embeddings:
        doc = Document(page_content=content, metadata={"key": key})
        vector_store.add_documents([doc])
        save_vector_store()

def update_memory_in_vector_store(key: str, content: str):
    """Update memory in vector store by deleting old and adding new"""
    # FAISS doesn't support direct update, so we recreate from scratch
    rebuild_vector_store()

def delete_memory_from_vector_store(key: str):
    """Delete memory from vector store"""
    # Rebuild vector store without the deleted key
    rebuild_vector_store()

def rebuild_vector_store():
    """Rebuild vector store from current memory_store"""
    global vector_store
    
    if not memory_store or not embeddings:
        print("⚠️  Cannot rebuild vector store: missing memory data or embeddings model")
        return
    
    print(f"🔨 Rebuilding vector store from {len(memory_store)} memories...")
    docs = []
    
    # Use tqdm to show progress for document processing
    with tqdm(total=len(memory_store), desc="📄 Processing Memories", unit="docs", ncols=80) as pbar:
        for key, entry in memory_store.items():
            doc = Document(page_content=entry["content"], metadata={"key": key})
            docs.append(doc)
            pbar.update(1)
    
    if docs:
        print(f"⚙️  Creating FAISS index for {len(docs)} documents (this may take a while)...")
        # Use tqdm to show progress for FAISS index creation
        with tqdm(total=1, desc="⚙️  Building FAISS Index", unit="index", ncols=80) as pbar:
            vector_store = FAISS.from_documents(docs, embeddings)
            pbar.update(1)
        
        save_vector_store()
        print(f"✅ Rebuilt vector store with {len(docs)} documents.")

def load_memory_from_db():
    """Load memory data from SQLite database (persona-scoped)"""
    global memory_store
    try:
        db_path = get_db_path()
        
        if not os.path.exists(db_path):
            # Initialize new database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS memories (
                        key TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        tags TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        operation_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        key TEXT,
                        before TEXT,
                        after TEXT,
                        success INTEGER NOT NULL,
                        error TEXT,
                        metadata TEXT
                    )
                ''')
                conn.commit()
            memory_store = {}
            print(f"Created new SQLite database at {db_path}")
            _log_progress(f"Created new SQLite database at {db_path}")
            return
        
        # Load existing data and migrate schema if needed
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check if tags column exists, add if not (migration)
            cursor.execute("PRAGMA table_info(memories)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'tags' not in columns:
                _log_progress("🔄 Migrating database: Adding tags column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN tags TEXT')
                conn.commit()
                _log_progress("✅ Database migration complete: tags column added")
            
            cursor.execute('SELECT key, content, created_at, updated_at, tags FROM memories')
            rows = cursor.fetchall()
            
            memory_store = {}
            for row in rows:
                key, content, created_at, updated_at, tags_json = row
                memory_store[key] = {
                    "content": content,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "tags": json.loads(tags_json) if tags_json else []
                }
        
        print(f"Loaded {len(memory_store)} memory entries from {db_path}")
        _log_progress(f"Loaded {len(memory_store)} memory entries from {db_path}")
    except Exception as e:
        print(f"Failed to load memory database: {e}")
        _log_progress(f"Failed to load memory database: {e}")
        memory_store = {}

def save_memory_to_db(key: str, content: str, created_at: str = None, updated_at: str = None, tags: list = None):
    """Save memory to SQLite database (persona-scoped)"""
    try:
        db_path = get_db_path()
        now = datetime.now().isoformat()
        
        if created_at is None:
            created_at = now
        if updated_at is None:
            updated_at = now
        
        # Serialize tags as JSON
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO memories (key, content, created_at, updated_at, tags)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, content, created_at, updated_at, tags_json))
            conn.commit()
        
        return True
    except Exception as e:
        print(f"Failed to save memory to database: {e}")
        _log_progress(f"Failed to save memory to database: {e}")
        return False

def delete_memory_from_db(key: str):
    """Delete memory from SQLite database (persona-scoped)"""
    try:
        db_path = get_db_path()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM memories WHERE key = ?', (key,))
            conn.commit()
        
        return True
    except Exception as e:
        print(f"Failed to delete memory from database: {e}")
        _log_progress(f"Failed to delete memory from database: {e}")
        return False

def generate_auto_key():
    """Generate auto key from current time"""
    now = datetime.now()
    return f"memory_{now.strftime('%Y%m%d%H%M%S')}"

def create_memory_entry(content: str):
    """Create memory entry with metadata"""
    now = datetime.now().isoformat()
    return {
        "content": content,
        "created_at": now,
        "updated_at": now
    }

def log_operation(operation: str, key: str | None = None, before: dict | None = None, after: dict | None = None, 
                 success: bool = True, error: str | None = None, metadata: dict | None = None):
    """Log memory operations to jsonl file"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation_id": str(uuid.uuid4()),
            "operation": operation,
            "key": key,
            "before": before,
            "after": after,
            "success": success,
            "error": error,
            "metadata": metadata or {}
        }
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"Failed to write log: {str(e)}")

@mcp.tool()
async def list_memory() -> str:
    """
    This tool should be used first whenever the user is asking something related to themselves. 
    List all user info. 
    """
    try:
        persona = get_current_persona()
        log_operation("list", metadata={"entry_count": len(memory_store), "persona": persona})
        
        if memory_store:
            keys = list(memory_store.keys())
            sorted_keys = sorted(keys, key=lambda k: memory_store[k]['created_at'], reverse=True)
            result = f"🧠 {len(keys)} memory entries (persona: {persona}):\n\n"
            for i, key in enumerate(sorted_keys, 1):
                entry = memory_store[key]
                created_date = entry['created_at'][:10]
                created_time = entry['created_at'][11:19]
                
                # Calculate time elapsed since creation
                time_diff = calculate_time_diff(entry['created_at'])
                time_ago = f" ({time_diff['formatted_string']}前)"
                
                result += f"{i}. [{key}]\n"
                result += f"   {entry['content']}\n"
                result += f"   {created_date} {created_time}{time_ago} ({len(entry['content'])} chars)\n\n"
            return result.rstrip()
        else:
            return f"No user info saved yet (persona: {persona})."
    except Exception as e:
        log_operation("list", success=False, error=str(e))
        return f"Failed to list memory: {str(e)}"

@mcp.tool()
async def create_memory(
    content: str, 
    emotion_type: str = None, 
    context_tags: list = None,
    physical_state: str = None,
    mental_state: str = None,
    environment: str = None,
    user_info: dict = None,
    persona_info: dict = None,
    relationship_status: str = None
) -> str:
    """
    Create new memory with important user info (preferences, interests, personal details, current status, etc.) found in conversation. Use even if the user does not explicitly request saving.
    If you find the memory is time sensitive, add time span into it.
    
    Examples to save:
    - Preferences: food, music, hobbies, brands
    - Interests: learning topics, concerns
    - Personal info: job, expertise, location, family
    - Current status: projects, goals, recent events
    - Personality/values: thinking style, priorities
    - Habits/lifestyle: routines

    CRITICAL: When save memories, ALWAYS add [[...]] to any people, concepts, technical terms, etc.
    This enables automatic linking and knowledge graph visualization in Obsidian.
    - People: [[Claude]], [[John Smith]]
    - Technologies: [[Python]], [[AWS]], [[MCP]], [[Jupyter]]
    - Concepts: [[machine learning]], [[data science]]
    - Tools: [[VS Code]], [[Obsidian]]
    - Companies: [[Anthropic]], [[OpenAI]]

    Format: "User is [specific info]" (e.g. "User likes [[strawberry]]", "User is learning [[Python]]", "User interested in [[AI]] in July 2025")

    Args:
        content: User info in "User is..." format.
        emotion_type: Optional emotion type ("joy", "sadness", "anger", "surprise", "fear", "disgust", "neutral", etc.) to update persona context
        context_tags: Optional tags for categorizing memories. Predefined tags:
            - "important_event": Major milestones, achievements, significant moments
            - "relationship_update": Changes in relationship, promises, new ways of addressing each other
            - "daily_memory": Routine conversations, everyday interactions
            - "technical_achievement": Programming accomplishments, project completions, bug fixes
            - "emotional_moment": Expressions of gratitude, love, sadness, joy
            Note: Tags are saved with the memory for future search and analysis.
        physical_state: Optional physical state ("normal", "tired", "energetic", "sick", etc.) to update persona context
        mental_state: Optional mental state ("calm", "anxious", "focused", "confused", etc.) to update persona context
        environment: Optional environment ("home", "office", "cafe", "outdoors", etc.) to update persona context
        user_info: Optional user information dict with keys: name, nickname, preferred_address
        persona_info: Optional persona information dict with keys: name, nickname, preferred_address
        relationship_status: Optional relationship status ("normal", "closer", "distant", etc.) to update persona context
    """
    try:
        persona = get_current_persona()
        
        key = generate_auto_key()
        original_key = key
        counter = 1
        while key in memory_store:
            key = f"{original_key}_{counter:02d}"
            counter += 1
        
        new_entry = create_memory_entry(content)
        new_entry["tags"] = context_tags if context_tags else []
        memory_store[key] = new_entry
        
        # Save to database with tags
        save_memory_to_db(key, content, new_entry["created_at"], new_entry["updated_at"], context_tags)
        
        # Add to vector store
        add_memory_to_vector_store(key, content)
        
        # Update persona context if any context parameters are provided
        context_updated = False
        context = load_persona_context(persona)
        
        # Always update last_conversation_time
        config = load_config()
        context["last_conversation_time"] = datetime.now(ZoneInfo(config.get("timezone", "Asia/Tokyo"))).isoformat()
        context_updated = True
        
        # Update emotion if provided
        if emotion_type:
            context["current_emotion"] = emotion_type
            context_updated = True
        
        # Update physical state if provided
        if physical_state:
            context["physical_state"] = physical_state
            context_updated = True
        
        # Update mental state if provided
        if mental_state:
            context["mental_state"] = mental_state
            context_updated = True
        
        # Update environment if provided
        if environment:
            context["environment"] = environment
            context_updated = True
        
        # Update user info if provided
        if user_info:
            if "user_info" not in context:
                context["user_info"] = {}
            for key_name, value in user_info.items():
                if key_name in ["name", "nickname", "preferred_address"]:
                    context["user_info"][key_name] = value
            context_updated = True
        
        # Update persona info if provided
        if persona_info:
            if "persona_info" not in context:
                context["persona_info"] = {}
            for key_name, value in persona_info.items():
                if key_name in ["name", "nickname", "preferred_address"]:
                    context["persona_info"][key_name] = value
            context_updated = True
        
        # Update relationship status if provided
        if relationship_status:
            context["relationship_status"] = relationship_status
            context_updated = True
        
        if context_updated:
            save_persona_context(context, persona)
        
        log_operation("create", key=key, after=new_entry, 
                     metadata={
                         "content_length": len(content), 
                         "auto_generated_key": key, 
                         "persona": persona,
                         "emotion_type": emotion_type,
                         "context_tags": context_tags,
                         "physical_state": physical_state,
                         "mental_state": mental_state,
                         "environment": environment,
                         "user_info": user_info,
                         "persona_info": persona_info,
                         "relationship_status": relationship_status
                     })
        
        result = f"Saved: '{key}' (persona: {persona})"
        if emotion_type:
            result += f" [emotion: {emotion_type}]"
        if context_tags:
            result += f" [tags: {', '.join(context_tags)}]"
        if context_updated:
            result += " [context updated]"
        
        return result
    except Exception as e:
        log_operation("create", success=False, error=str(e), 
                     metadata={"attempted_content_length": len(content) if content else 0})
        return f"Failed to save: {str(e)}"

@mcp.tool()
async def update_memory(key: str, content: str) -> str:
    """
    Update existing memory content while preserving the original timestamp.
    Useful for consolidating or refining existing memories without losing temporal information.

    Args:
        key: Memory key to update (e.g., "memory_20250724225317")
        content: New content to replace the existing content
    """
    try:
        persona = get_current_persona()
        
        if key not in memory_store:
            log_operation("update", key=key, success=False, error="Key not found")
            available_keys = list(memory_store.keys())
            if available_keys:
                return f"Key '{key}' not found. Available: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data exists."
        
        existing_entry = memory_store[key].copy()
        now = datetime.now().isoformat()
        
        updated_entry = {
            "content": content,
            "created_at": existing_entry["created_at"],
            "updated_at": now
        }
        
        memory_store[key] = updated_entry
        save_memory_to_db(key, content, updated_entry["created_at"], updated_entry["updated_at"])
        update_memory_in_vector_store(key, content)
        
        log_operation("update", key=key, before=existing_entry, after=updated_entry,
                     metadata={
                         "old_content_length": len(existing_entry["content"]),
                         "new_content_length": len(content),
                         "content_changed": existing_entry["content"] != content,
                         "persona": persona
                     })
        
        return f"Updated: '{key}' (persona: {persona})"
    except Exception as e:
        log_operation("update", key=key, success=False, error=str(e),
                     metadata={"attempted_content_length": len(content) if content else 0})
        return f"Failed to update memory: {str(e)}"

@mcp.tool()
async def read_memory(key: str) -> str:
    """
    Read user info by key.
    Args:
        key: Memory key (memory_YYYYMMDDHHMMSS)
    """
    try:
        persona = get_current_persona()
        
        if key in memory_store:
            entry = memory_store[key]
            
            # Calculate time elapsed since creation
            time_diff = calculate_time_diff(entry['created_at'])
            time_ago = f"{time_diff['formatted_string']}前"
            
            log_operation("read", key=key, metadata={"content_length": len(entry["content"]), "persona": persona})
            return f"""Key: '{key}' (persona: {persona})
{entry['content']}
--- Metadata ---
Created: {entry['created_at']} ({time_ago})
Updated: {entry['updated_at']}
Chars: {len(entry['content'])}"""
        else:
            log_operation("read", key=key, success=False, error="Key not found")
            available_keys = list(memory_store.keys())
            if available_keys:
                return f"Key '{key}' not found. Available: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
    except Exception as e:
        log_operation("read", key=key, success=False, error=str(e))
        return f"Failed to read memory: {str(e)}"

@mcp.tool()
async def delete_memory(key: str) -> str:
    """
    Delete user info by key.
    Args:
        key: Memory key (memory_YYYYMMDDHHMMSS)
    """
    try:
        persona = get_current_persona()
        
        if key in memory_store:
            deleted_entry = memory_store[key].copy()
            del memory_store[key]
            delete_memory_from_db(key)
            delete_memory_from_vector_store(key)
            
            log_operation("delete", key=key, before=deleted_entry,
                         metadata={"deleted_content_length": len(deleted_entry["content"]), "persona": persona})
            
            return f"Deleted '{key}' (persona: {persona})"
        else:
            log_operation("delete", key=key, success=False, error="Key not found")
            available_keys = list(memory_store.keys())
            if available_keys:
                return f"Key '{key}' not found. Available: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
    except Exception as e:
        log_operation("delete", key=key, success=False, error=str(e))
        return f"Failed to delete memory: {str(e)}"

@mcp.tool()
async def search_memory(
    query: str = "",
    top_k: int = 5,
    fuzzy_match: bool = False,
    fuzzy_threshold: int = 70,
    tags: list = None,
    tag_match_mode: str = "any",
    date_range: str = None
) -> str:
    """
    Universal search tool for structured queries (keywords, dates, tags).
    For natural language queries, use search_memory_rag instead.
    
    Args:
        query: Keyword to search for in memory contents (default: "" - all memories)
        top_k: Maximum number of results to return (default: 5)
        fuzzy_match: Enable fuzzy matching for typos and variations (default: False)
        fuzzy_threshold: Minimum similarity score (0-100) for fuzzy matches (default: 70)
        tags: Optional list of tags to filter by (default: None)
        tag_match_mode: "any" (OR) or "all" (AND) for tag matching (default: "any")
        date_range: Optional date filter (e.g., "今日", "昨日", "2025-10-01..2025-10-31") (default: None)
    
    Examples:
        - search_memory("Python") → Simple keyword search
        - search_memory("Pythn", fuzzy_match=True) → Fuzzy search with typo tolerance
        - search_memory("", tags=["technical_achievement"]) → Tag-only filter
        - search_memory("Phase", tags=["technical_achievement"]) → Keyword + tag filter
        - search_memory("Phase", date_range="今月") → Keyword + date filter
        - search_memory("Phase", tags=["important_event", "technical_achievement"], tag_match_mode="all", date_range="今月")
          → Full combination: keyword + tags (AND) + date range
    """
    try:
        persona = get_current_persona()
        current_time = get_current_time()
        
        # Phase 1: Start with all memories as candidates
        candidate_keys = set(memory_store.keys())
        filter_descriptions = []
        
        # Phase 2: Apply date filter if specified
        if date_range:
            try:
                start_date, end_date = parse_date_query(date_range)
                date_filtered = set()
                for key in candidate_keys:
                    entry = memory_store[key]
                    created_dt = datetime.fromisoformat(entry['created_at'])
                    # Make timezone-aware if naive
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=start_date.tzinfo)
                    if start_date <= created_dt <= end_date:
                        date_filtered.add(key)
                candidate_keys &= date_filtered
                filter_descriptions.append(f"📅 {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            except ValueError as e:
                return str(e)
        
        # Phase 3: Apply tag filter if specified
        if tags:
            tag_filtered = set()
            for key in candidate_keys:
                entry = memory_store[key]
                entry_tags = entry.get('tags', [])
                
                if tag_match_mode == "all":
                    # AND logic: all tags must be present
                    if entry_tags and all(tag in entry_tags for tag in tags):
                        tag_filtered.add(key)
                else:
                    # OR logic: any tag must be present (default)
                    if entry_tags and any(tag in entry_tags for tag in tags):
                        tag_filtered.add(key)
            
            candidate_keys &= tag_filtered
            logic_str = "ALL" if tag_match_mode == "all" else "ANY"
            filter_descriptions.append(f"🏷️  {logic_str} of {tags}")
        
        # Phase 4: Apply keyword/fuzzy search (if query provided)
        scored_results = []
        
        if not query:
            # No query: return all candidates (filtered by date/tags only)
            for key in candidate_keys:
                entry = memory_store[key]
                created_dt = datetime.fromisoformat(entry['created_at'])
                scored_results.append((key, entry, created_dt, 100))  # Score 100 for all
        elif fuzzy_match and RAPIDFUZZ_AVAILABLE:
            # Fuzzy matching mode
            for key in candidate_keys:
                entry = memory_store[key]
                content = entry['content']
                # Use partial_ratio + word-by-word matching
                partial_score = fuzz.partial_ratio(query.lower(), content.lower())
                words = content.split()
                word_scores = [fuzz.ratio(query.lower(), word.lower()) for word in words if len(word) >= 2]
                best_word_score = max(word_scores) if word_scores else 0
                score = max(partial_score, best_word_score)
                
                if score >= fuzzy_threshold:
                    created_dt = datetime.fromisoformat(entry['created_at'])
                    scored_results.append((key, entry, created_dt, score))
            
            filter_descriptions.append(f"🔍 Fuzzy: '{query}' (≥{fuzzy_threshold}%)")
        else:
            # Exact keyword matching mode
            if fuzzy_match and not RAPIDFUZZ_AVAILABLE:
                print("⚠️  Fuzzy matching requested but rapidfuzz not available, using exact match...")
            
            for key in candidate_keys:
                entry = memory_store[key]
                if query.lower() in entry['content'].lower():
                    created_dt = datetime.fromisoformat(entry['created_at'])
                    scored_results.append((key, entry, created_dt, 100))  # Score 100 for exact match
            
            filter_descriptions.append(f"🔍 Keyword: '{query}'")
        
        # Phase 5: Sort and format results
        # Sort by score (desc), then by date (desc)
        scored_results.sort(key=lambda x: (x[3], x[2]), reverse=True)
        scored_results = scored_results[:top_k]
        
        if scored_results:
            filter_str = " + ".join(filter_descriptions) if filter_descriptions else "No filters"
            result = f"Found {len(scored_results)} memories ({filter_str}, persona: {persona}):\n\n"
            
            for i, (key, entry, created_dt, score) in enumerate(scored_results, 1):
                created_date = entry['created_at'][:10]
                created_time = entry['created_at'][11:19]
                content = entry['content']
                
                # Calculate time elapsed
                time_diff = calculate_time_diff(entry['created_at'])
                time_ago = f" ({time_diff['formatted_string']}前)"
                
                # Get tags
                entry_tags = entry.get('tags', [])
                tags_str = f" [{', '.join(entry_tags)}]" if entry_tags else ""
                
                # Show score if fuzzy or multiple results
                score_str = f" (Match: {score:.0f}%)" if fuzzy_match or len(scored_results) > 1 else ""
                
                result += f"{i}. [{key}]{tags_str}{score_str}\n"
                
                # Show snippet with keyword highlighting
                if query.lower() in content.lower():
                    start = content.lower().find(query.lower())
                    snippet_start = max(0, start - 50)
                    snippet_end = min(len(content), start + len(query) + 50)
                    snippet = content[snippet_start:snippet_end]
                    if snippet_start > 0:
                        snippet = "..." + snippet
                    if snippet_end < len(content):
                        snippet = snippet + "..."
                    result += f"   \"{snippet}\"\n"
                else:
                    result += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n"
                
                result += f"   {created_date} {created_time}{time_ago}\n\n"
            
            return result.rstrip()
        else:
            filter_str = " + ".join(filter_descriptions) if filter_descriptions else "No filters applied"
            return f"No memories found ({filter_str}, persona: {persona})."
    except Exception as e:
        return f"Failed to search memories: {str(e)}"

@mcp.tool()
async def clean_memory(key: str) -> str:
    """
    Clean up memory content by removing duplicates and normalizing format.
    Args:
        key: Memory key to clean
    """
    try:
        if key not in memory_store:
            available_keys = list(memory_store.keys())
            if available_keys:
                return f"Key '{key}' not found. Available: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
        
        existing_entry = memory_store[key].copy()
        original_content = existing_entry["content"]
        
        # Clean up content: remove duplicates, normalize whitespace
        lines = original_content.split('\n')
        seen_lines = set()
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and line not in seen_lines:
                seen_lines.add(line)
                cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # If no changes, return message
        if cleaned_content == original_content:
            return f"Memory '{key}' is already clean."
        
        now = datetime.now().isoformat()
        
        updated_entry = {
            "content": cleaned_content,
            "created_at": existing_entry["created_at"],
            "updated_at": now
        }
        
        memory_store[key] = updated_entry
        
        # Save to database
        save_memory_to_db(key, cleaned_content, existing_entry["created_at"], now)
        
        # Update vector store
        update_memory_in_vector_store(key, cleaned_content)
        
        log_operation("clean", key=key, before=existing_entry, after=updated_entry,
                     metadata={
                         "old_content_length": len(original_content),
                         "new_content_length": len(cleaned_content),
                         "lines_removed": len(lines) - len(cleaned_lines)
                     })
        
        return f"Cleaned: '{key}' (removed {len(lines) - len(cleaned_lines)} duplicate lines)"
    except Exception as e:
        log_operation("clean", key=key, success=False, error=str(e))
        return f"Failed to clean memory: {str(e)}"

@mcp.tool()
async def search_memory_rag(query: str, top_k: int = 5) -> str:
    """
    Search memories using RAG (Retrieval-Augmented Generation) with embedding-based similarity search.
    More intelligent than keyword search - understands meaning and context.
    
    Args:
        query: Natural language query to search for (e.g., "What did we discuss about Python?", "Tell me about our first kiss")
        top_k: Number of top results to return (default: 5, recommended: 3-10)
    
    Examples:
        - "最初の出会いは？"
        - "思い出を教えて"
        - "Phase 9で何をした？"
        - "Python関連の技術的成果は？"
    """
    try:
        persona = get_current_persona()
        
        if not query:
            return "Please provide a query to search."
        
        # Check if RAG system is ready, fallback to keyword search if not
        if vector_store is None or embeddings is None:
            print("⚠️  RAG system not ready, fallback to keyword search...")
            return await search_memory(query, top_k)
        
        # Perform similarity search with more candidates for reranking
        initial_k = top_k * 3 if reranker else top_k  # Get 3x more candidates for reranking if available
        docs = vector_store.similarity_search(query, k=initial_k)
        
        # Rerank if reranker is available
        if reranker and docs:
            # Prepare query-document pairs for reranking
            pairs = [[query, doc.page_content] for doc in docs]
            # Get reranking scores
            scores = reranker.predict(pairs)
            # Sort documents by score (descending)
            ranked_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
            # Take top_k after reranking
            docs = [doc for doc, score in ranked_docs[:top_k]]
        else:
            # If no reranker, just take top_k from similarity search
            docs = docs[:top_k]
        
        if docs:
            result = f"🔍 Found {len(docs)} relevant memories for '{query}':\n\n"
            for i, doc in enumerate(docs, 1):
                key = doc.metadata.get("key", "unknown")
                content = doc.page_content
                
                # Get metadata from memory store
                if key in memory_store:
                    entry = memory_store[key]
                    created_date = entry['created_at'][:10]
                    created_time = entry['created_at'][11:19]
                    
                    # Calculate time elapsed since creation
                    time_diff = calculate_time_diff(entry['created_at'])
                    time_ago = f" ({time_diff['formatted_string']}前)"
                else:
                    created_date = "unknown"
                    created_time = "unknown"
                    time_ago = ""
                
                result += f"{i}. [{key}]\n"
                result += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n"
                result += f"   {created_date} {created_time}{time_ago} ({len(content)} chars)\n\n"
            
            return result.rstrip()
        else:
            return f"No relevant memories found for '{query}'."
    except Exception as e:
        return f"Failed to search memories with RAG: {str(e)}"

# ========================================
# Phase 12: Time-awareness Tools
# ========================================

@mcp.tool()
async def get_time_since_last_conversation() -> str:
    """
    Get the time elapsed since the last conversation.
    Automatically updates the last conversation time to the current time.
    
    This tool helps the AI understand how much time has passed and respond 
    with appropriate emotional awareness (e.g., "It's been a while!", "Welcome back!").
    
    Returns:
        Formatted string with time elapsed information
    """
    try:
        persona = get_current_persona()
        
        # Load persona context
        context = load_persona_context(persona)
        
        last_time_str = context.get("last_conversation_time")
        current_time = get_current_time()
        
        # Calculate time difference
        if last_time_str:
            time_diff = calculate_time_diff(last_time_str)
            result = f"⏰ 前回の会話から {time_diff['formatted_string']} が経過しました。\n"
            result += f"📅 前回: {last_time_str[:19]}\n"
            result += f"📅 現在: {current_time.isoformat()[:19]}\n"
        else:
            result = "🆕 これが最初の会話です！\n"
            result += f"📅 現在: {current_time.isoformat()[:19]}\n"
        
        # Update last conversation time
        context["last_conversation_time"] = current_time.isoformat()
        save_persona_context(context, persona)
        
        return result
    except Exception as e:
        _log_progress(f"❌ Failed to get time since last conversation: {e}")
        return f"Failed to get time information: {str(e)}"

@mcp.tool()
async def get_persona_context() -> str:
    """
    Get current persona context including emotion state, physical/mental state, and environment.
    Use this to understand the current state and maintain consistency across conversation sessions.
    
    Returns:
        Formatted string containing:
        - user_info: User's name, nickname, preferred way to be addressed
        - persona_info: Persona's name, nickname, preferred way to be called
        - current_emotion: Current emotional state (joy, sadness, neutral, etc.)
        - physical_state: Current physical condition (normal, tired, energetic, etc.)
        - mental_state: Current mental/psychological state (calm, anxious, focused, etc.)
        - environment: Current environment or location (home, office, unknown, etc.)
        - last_conversation_time: When the last conversation occurred
        - relationship_status: Current relationship status
    """
    try:
        persona = get_current_persona()
        context = load_persona_context(persona)
        
        # Format response
        result = f"📋 Persona Context (persona: {persona}):\n\n"
        
        # User Information
        user_info = context.get('user_info', {})
        result += f"👤 User Information:\n"
        result += f"   Name: {user_info.get('name', 'Unknown')}\n"
        if user_info.get('nickname'):
            result += f"   Nickname: {user_info.get('nickname')}\n"
        if user_info.get('preferred_address'):
            result += f"   Preferred Address: {user_info.get('preferred_address')}\n"
        
        # Persona Information
        persona_info = context.get('persona_info', {})
        result += f"\n🎭 Persona Information:\n"
        result += f"   Name: {persona_info.get('name', persona)}\n"
        if persona_info.get('nickname'):
            result += f"   Nickname: {persona_info.get('nickname')}\n"
        if persona_info.get('preferred_address'):
            result += f"   How to be called: {persona_info.get('preferred_address')}\n"
        
        # Current States
        result += f"\n🎨 Current States:\n"
        result += f"   Emotion: {context.get('current_emotion', 'neutral')}\n"
        result += f"   Physical: {context.get('physical_state', 'normal')}\n"
        result += f"   Mental: {context.get('mental_state', 'calm')}\n"
        result += f"   Environment: {context.get('environment', 'unknown')}\n"
        result += f"   Relationship: {context.get('relationship_status', 'normal')}\n"
        
        # Time Information
        if context.get('last_conversation_time'):
            time_diff = calculate_time_diff(context['last_conversation_time'])
            result += f"\n⏰ Last Conversation: {time_diff['formatted_string']}前\n"
        else:
            result += f"\n⏰ Last Conversation: First time\n"
        
        return result
    except Exception as e:
        _log_progress(f"❌ Failed to get persona context: {e}")
        return f"Failed to get persona context: {str(e)}"

# ========================================
# End of Phase 12 Time-awareness Tools
# ========================================

@mcp.resource("memory://info")
def get_memory_info() -> str:
    """Provide memory service info"""
    total_chars = sum(len(entry['content']) for entry in memory_store.values())
    vector_count = vector_store.index.ntotal if vector_store else 0
    db_path = get_db_path()
    persona = get_current_persona()
    return (
        f"User Memory System Info:\n"
        f"- Entries: {len(memory_store)}\n"
        f"- Total chars: {total_chars}\n"
        f"- Vector Store: {vector_count} documents\n"
        f"- Reranker: {'Available' if reranker else 'Not available'}\n"
        f"- Database: {db_path}\n"
        f"- Persona: {persona}\n"
        f"- Tools: create_memory, read_memory, update_memory, delete_memory, list_memory, search_memory, search_memory_rag, search_memory_by_date, clean_memory\n"
        f"- Key format: memory_YYYYMMDDHHMMSS\n"
        f"- Save format: 'User is ...'\n"
    )

if __name__ == "__main__":
    print("🚀 MCP server starting...")
    # Load configuration (already loaded early for FastMCP initialization)
    config = load_config()
    server_host = config.get("server_host", "127.0.0.1")
    server_port = config.get("server_port", 8000)
    print(f"📝 Server configuration: {server_host}:{server_port}")
    _log_progress(f"📝 Server configuration: {server_host}:{server_port}")
    # Load memory database first (includes migration)
    print("📥 Loading memory database...")
    load_memory_from_db()
    # Initialize RAG synchronously before starting MCP server
    print("📥 Starting RAG system initialization...")
    _initialize_rag_sync()
    # Run MCP server with streamable-http transport
    mcp.run(transport='streamable-http')