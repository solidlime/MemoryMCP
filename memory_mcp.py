import asyncio
import json
import os
import sys
import uuid
import shutil
import sqlite3
import warnings
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from mcp.server.fastmcp import FastMCP
from db_utils import db_get_entry as _db_get_entry_generic, db_recent_keys as _db_recent_keys_generic, db_count_entries as _db_count_entries_generic, db_sum_content_chars as _db_sum_content_chars_generic
from persona_utils import (
    current_persona,
    get_current_persona,
    get_persona_dir,
    get_db_path,
    get_vector_store_path,
    get_persona_context_path,
)
from vector_utils import (
    initialize_rag_sync as _initialize_rag_sync,
    add_memory_to_vector_store,
    update_memory_in_vector_store,
    delete_memory_from_vector_store,
    rebuild_vector_store,
    start_idle_rebuilder_thread,
    get_vector_count,
    get_vector_metrics,
)
from vector_utils import reranker as _reranker

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

# LangChain & RAG imports (Document only used for dummy doc snippets)
from langchain_core.documents import Document
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

"""Persona helpers are imported from persona_utils"""

LOG_FILE = os.path.join(SCRIPT_DIR, "memory_operations.log")

memory_store = {}

def _get_rebuild_config():
    cfg = load_config() or {}
    vr = cfg.get("vector_rebuild", {}) if isinstance(cfg, dict) else {}
    return {
        "mode": vr.get("mode", "idle"),
        "idle_seconds": int(vr.get("idle_seconds", 30)),
        "min_interval": int(vr.get("min_interval", 120)),
    }

"""Vector store idle rebuild handled in vector_utils"""

def _log_progress(message: str):
    """Log progress message to file (avoiding MCP protocol interference)"""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] PROGRESS: {message}\n")
    except Exception:
        pass  # Silently fail if logging fails

"""Persona path helpers are imported from persona_utils"""

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

"""Vector/RAG initialization and rebuild now handled by vector_utils"""

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
        persona = get_current_persona()
        db_path = get_db_path()
        _log_progress(f"💾 Attempting to save to DB: {db_path} (persona: {persona})")
        
        now = datetime.now().isoformat()
        
        if created_at is None:
            created_at = now
        if updated_at is None:
            updated_at = now
        
        # Serialize tags as JSON
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        _log_progress(f"💾 Tags JSON: {tags_json}")
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check schema before insert
            cursor.execute("PRAGMA table_info(memories)")
            columns = [col[1] for col in cursor.fetchall()]
            _log_progress(f"💾 DB columns: {columns}")
            
            cursor.execute('''
                INSERT OR REPLACE INTO memories (key, content, created_at, updated_at, tags)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, content, created_at, updated_at, tags_json))
            conn.commit()
            _log_progress(f"✅ Successfully saved {key} to DB")
        
        return True
    except Exception as e:
        print(f"Failed to save memory to database: {e}")
        _log_progress(f"❌ Failed to save memory to database: {e}")
        _log_progress(f"❌ DB path was: {db_path}")
        import traceback
        _log_progress(f"❌ Traceback: {traceback.format_exc()}")
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

# ---------------------------
# DB helper utilities (refactor)
# ---------------------------
def db_get_entry(key: str):
    """Wrapper to generic helper with current persona db_path"""
    return _db_get_entry_generic(get_db_path(), key)

def db_recent_keys(limit: int = 5) -> list:
    return _db_recent_keys_generic(get_db_path(), limit)

def db_count_entries() -> int:
    return _db_count_entries_generic(get_db_path())

def db_sum_content_chars() -> int:
    return _db_sum_content_chars_generic(get_db_path())

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

async def list_memory() -> str:
    """
    This tool should be used first whenever the user is asking something related to themselves. 
    List all user info. 
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Read directly from database instead of memory_store
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, content, created_at, updated_at, tags FROM memories ORDER BY created_at DESC')
            rows = cursor.fetchall()
        
        log_operation("list", metadata={"entry_count": len(rows), "persona": persona})
        
        if rows:
            result = f"🧠 {len(rows)} memory entries (persona: {persona}):\n\n"
            for i, row in enumerate(rows, 1):
                key, content, created_at, updated_at, tags_json = row
                created_date = created_at[:10]
                created_time = created_at[11:19]
                
                # Calculate time elapsed since creation
                time_diff = calculate_time_diff(created_at)
                time_ago = f" ({time_diff['formatted_string']}前)"
                
                result += f"{i}. [{key}]\n"
                result += f"   {content}\n"
                result += f"   {created_date} {created_time}{time_ago} ({len(content)} chars)\n\n"
            return result.rstrip()
        else:
            return f"No user info saved yet (persona: {persona})."
    except Exception as e:
        log_operation("list", success=False, error=str(e))
        return f"Failed to list memory: {str(e)}"

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
        db_path = get_db_path()
        
        # Generate unique key by checking database
        key = generate_auto_key()
        original_key = key
        counter = 1
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Check if key exists in database
            while True:
                cursor.execute('SELECT COUNT(*) FROM memories WHERE key = ?', (key,))
                if cursor.fetchone()[0] == 0:
                    break
                key = f"{original_key}_{counter:02d}"
                counter += 1
        
        new_entry = create_memory_entry(content)
        new_entry["tags"] = context_tags if context_tags else []
        
        # Save to database with tags (no longer updating memory_store)
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
        db_path = get_db_path()
        
        # Check if key exists in database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content, created_at, tags FROM memories WHERE key = ?', (key,))
            row = cursor.fetchone()
        
        if not row:
            log_operation("update", key=key, success=False, error="Key not found")
            # Get available keys
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key FROM memories ORDER BY created_at DESC LIMIT 5')
                available_keys = [r[0] for r in cursor.fetchall()]
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data exists."
        
        old_content, created_at, tags_json = row
        existing_entry = {
            "content": old_content,
            "created_at": created_at,
            "tags": json.loads(tags_json) if tags_json else []
        }
        
        now = datetime.now().isoformat()
        updated_entry = {
            "content": content,
            "created_at": created_at,
            "updated_at": now
        }
        
        # Update in database (preserve tags)
        save_memory_to_db(key, content, created_at, now, existing_entry["tags"])
        update_memory_in_vector_store(key, content)
        
        log_operation("update", key=key, before=existing_entry, after=updated_entry,
                     metadata={
                         "old_content_length": len(old_content),
                         "new_content_length": len(content),
                         "content_changed": old_content != content,
                         "persona": persona
                     })
        
        return f"Updated: '{key}' (persona: {persona})"
    except Exception as e:
        log_operation("update", key=key, success=False, error=str(e),
                     metadata={"attempted_content_length": len(content) if content else 0})
        return f"Failed to update memory: {str(e)}"

async def read_memory(key: str) -> str:
    """
    Read user info by key.
    Args:
        key: Memory key (memory_YYYYMMDDHHMMSS)
    """
    try:
        persona = get_current_persona()
        # Read directly from database via helper
        row = db_get_entry(key)
        
        if row:
            content, created_at, updated_at, tags_json = row
            
            # Calculate time elapsed since creation
            time_diff = calculate_time_diff(created_at)
            time_ago = f"{time_diff['formatted_string']}前"
            
            log_operation("read", key=key, metadata={"content_length": len(content), "persona": persona})
            return f"""Key: '{key}' (persona: {persona})
{content}
--- Metadata ---
Created: {created_at} ({time_ago})
Updated: {updated_at}
Chars: {len(content)}"""
        else:
            log_operation("read", key=key, success=False, error="Key not found")
            # Get available keys from DB
            available_keys = db_recent_keys(5)
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
    except Exception as e:
        log_operation("read", key=key, success=False, error=str(e))
        return f"Failed to read memory: {str(e)}"

async def delete_memory(key: str) -> str:
    """
    Delete user info by key.
    Args:
        key: Memory key (memory_YYYYMMDDHHMMSS)
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Check if key exists and get data
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content FROM memories WHERE key = ?', (key,))
            row = cursor.fetchone()
        
        if row:
            deleted_content = row[0]
            deleted_entry = {"content": deleted_content}
            
            delete_memory_from_db(key)
            delete_memory_from_vector_store(key)
            
            log_operation("delete", key=key, before=deleted_entry,
                         metadata={"deleted_content_length": len(deleted_content), "persona": persona})
            
            return f"Deleted '{key}' (persona: {persona})"
        else:
            log_operation("delete", key=key, success=False, error="Key not found")
            # Get available keys
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key FROM memories ORDER BY created_at DESC LIMIT 5')
                available_keys = [r[0] for r in cursor.fetchall()]
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
    except Exception as e:
        log_operation("delete", key=key, success=False, error=str(e))
        return f"Failed to delete memory: {str(e)}"

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
        db_path = get_db_path()
        
        # Read all memories from database
        memories = {}
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, content, created_at, updated_at, tags FROM memories')
            for row in cursor.fetchall():
                key, content, created_at, updated_at, tags_json = row
                memories[key] = {
                    "content": content,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "tags": json.loads(tags_json) if tags_json else []
                }
        
        # Phase 1: Start with all memories as candidates
        candidate_keys = set(memories.keys())
        filter_descriptions = []
        
        # Phase 2: Apply date filter if specified
        if date_range:
            try:
                start_date, end_date = parse_date_query(date_range)
                date_filtered = set()
                for key in candidate_keys:
                    entry = memories[key]
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
                entry = memories[key]
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
                entry = memories[key]
                created_dt = datetime.fromisoformat(entry['created_at'])
                scored_results.append((key, entry, created_dt, 100))  # Score 100 for all
        elif fuzzy_match and RAPIDFUZZ_AVAILABLE:
            # Fuzzy matching mode
            for key in candidate_keys:
                entry = memories[key]
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
                entry = memories[key]
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

async def clean_memory(key: str) -> str:
    """
    Clean up memory content by removing duplicates and normalizing format.
    Args:
        key: Memory key to clean
    """
    try:
        db_path = get_db_path()
        
        # Get memory from database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content, created_at, tags FROM memories WHERE key = ?', (key,))
            row = cursor.fetchone()
        
        if not row:
            # Get available keys
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key FROM memories ORDER BY created_at DESC LIMIT 5')
                available_keys = [r[0] for r in cursor.fetchall()]
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
        
        original_content, created_at, tags_json = row
        existing_tags = json.loads(tags_json) if tags_json else []
        
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
        
        # Save to database (preserve tags and created_at)
        save_memory_to_db(key, cleaned_content, created_at, now, existing_tags)
        
        # Update vector store
        update_memory_in_vector_store(key, cleaned_content)
        
        log_operation("clean", key=key, 
                     before={"content": original_content, "created_at": created_at, "tags": existing_tags},
                     after={"content": cleaned_content, "created_at": created_at, "updated_at": now, "tags": existing_tags},
                     metadata={
                         "old_content_length": len(original_content),
                         "new_content_length": len(cleaned_content),
                         "lines_removed": len(lines) - len(cleaned_lines)
                     })
        
        return f"Cleaned: '{key}' (removed {len(lines) - len(cleaned_lines)} duplicate lines)"
    except Exception as e:
        log_operation("clean", key=key, success=False, error=str(e))
        return f"Failed to clean memory: {str(e)}"

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
        from vector_utils import vector_store, embeddings, reranker
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
            persona = get_current_persona()
            db_path = get_db_path()
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                for i, doc in enumerate(docs, 1):
                    key = doc.metadata.get("key", "unknown")
                    content = doc.page_content
                    # DBからメタデータ取得
                    cursor.execute('SELECT created_at FROM memories WHERE key = ?', (key,))
                    row = cursor.fetchone()
                    if row:
                        created_at = row[0]
                        created_date = created_at[:10]
                        created_time = created_at[11:19]
                        time_diff = calculate_time_diff(created_at)
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

async def rebuild_vector_store_tool() -> str:
    """
    Rebuild vector store from database.
    Use this when search_memory_rag returns outdated or missing results.
    This will recreate the FAISS index from all memories in the current persona's database.
    """
    try:
        persona = get_current_persona()
        rebuild_vector_store()
        return f"✅ Vector store rebuilt successfully for persona: {persona}"
    except Exception as e:
        return f"❌ Failed to rebuild vector store: {str(e)}"

# ========================================
# Tool: Find Related Memories
# ========================================

async def find_related_memories(
    memory_key: str,
    top_k: int = 5
) -> str:
    """
    Find memories related to the specified memory using embeddings similarity.
    
    This tool helps discover connections between memories by analyzing semantic similarity.
    Useful for:
    - Finding relevant context for a specific memory
    - Discovering related topics or experiences
    - Understanding memory clusters and themes
    
    Args:
        memory_key: The key of the memory to find related memories for (format: memory_YYYYMMDDHHMMSS)
        top_k: Number of related memories to return (default: 5, max: 20)
        
    Returns:
        Formatted string with related memories and their similarity scores
    """
    from vector_utils import find_similar_memories
    
    try:
        persona = get_current_persona()
        
        # Validate input
        if not memory_key.startswith("memory_"):
            return "❌ Invalid memory key format. Expected: memory_YYYYMMDDHHMMSS"
        
        # Limit top_k to reasonable range
        top_k = min(max(1, top_k), 20)
        
        # Check if memory exists
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content, created_at FROM memories WHERE key = ?", (memory_key,))
            row = cursor.fetchone()
            
        if not row:
            return f"❌ Memory not found: {memory_key}"
        
        query_content, created_at = row
        
        # Find similar memories
        similar = find_similar_memories(memory_key, top_k)
        
        if not similar:
            return f"💡 No related memories found for {memory_key}"
        
        # Format output
        result = f"🔗 Related Memories for {memory_key}:\n"
        result += f"📝 Query: {query_content[:100]}{'...' if len(query_content) > 100 else ''}\n"
        result += f"📅 Created: {created_at}\n"
        result += f"\n{'='*50}\n"
        result += f"Found {len(similar)} related memories:\n\n"
        
        for idx, (key, content, score) in enumerate(similar, 1):
            # Get timestamp for related memory
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT created_at FROM memories WHERE key = ?", (key,))
                ts_row = cursor.fetchone()
                timestamp = ts_row[0] if ts_row else "Unknown"
            
            # Calculate time difference
            time_diff = calculate_time_diff(timestamp)
            
            result += f"{idx}. [{key}] (similarity: {score:.3f})\n"
            result += f"   📅 {time_diff['formatted_string']}前\n"
            result += f"   📝 {content[:150]}{'...' if len(content) > 150 else ''}\n\n"
        
        result += f"\n💡 Persona: {persona}"
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to find related memories: {e}")
        return f"❌ Error finding related memories: {str(e)}"

# ========================================
# Tool: Detect Duplicate Memories
# ========================================

async def detect_duplicates(
    threshold: float = 0.85,
    max_pairs: int = 50
) -> str:
    """
    Detect duplicate or highly similar memory pairs.
    
    This tool helps identify memories that are very similar to each other,
    which might be:
    - Exact duplicates created by mistake
    - Multiple versions of the same information
    - Related memories that could be merged
    
    Args:
        threshold: Similarity threshold (0.0-1.0). Default 0.85 means 85% similar or more.
                  Higher values = stricter duplicate detection (only very similar pairs)
                  Lower values = looser detection (more pairs, including somewhat similar ones)
        max_pairs: Maximum number of duplicate pairs to return (default: 50)
        
    Returns:
        Formatted string with duplicate pairs sorted by similarity
    """
    from vector_utils import detect_duplicate_memories
    
    try:
        persona = get_current_persona()
        
        # Validate threshold
        threshold = max(0.0, min(1.0, threshold))
        max_pairs = max(1, min(100, max_pairs))
        
        # Detect duplicates
        duplicates = detect_duplicate_memories(threshold, max_pairs)
        
        if not duplicates:
            return f"💡 No duplicate memories found (threshold: {threshold:.2f})\n\nTry lowering the threshold to find more similar pairs."
        
        # Format output
        result = f"🔍 Duplicate Memory Detection (persona: {persona})\n"
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"Threshold: {threshold:.2f} (similarity ≥ {threshold*100:.0f}%)\n"
        result += f"Found {len(duplicates)} duplicate pairs:\n\n"
        
        for idx, (key1, key2, content1, content2, similarity) in enumerate(duplicates, 1):
            # Get timestamps
            db_path = get_db_path()
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT created_at FROM memories WHERE key = ?", (key1,))
                ts1 = cursor.fetchone()[0]
                cursor.execute("SELECT created_at FROM memories WHERE key = ?", (key2,))
                ts2 = cursor.fetchone()[0]
            
            time_diff1 = calculate_time_diff(ts1)
            time_diff2 = calculate_time_diff(ts2)
            
            result += f"━━━ Pair {idx} (similarity: {similarity:.3f} = {similarity*100:.1f}%) ━━━\n\n"
            result += f"📝 Memory 1: [{key1}] ({time_diff1['formatted_string']}前)\n"
            result += f"   {content1[:200]}{'...' if len(content1) > 200 else ''}\n\n"
            result += f"📝 Memory 2: [{key2}] ({time_diff2['formatted_string']}前)\n"
            result += f"   {content2[:200]}{'...' if len(content2) > 200 else ''}\n\n"
        
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"💡 Tip: Use merge_memories tool to combine duplicate pairs.\n"
        result += f"💡 Persona: {persona}"
        
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to detect duplicates: {e}")
        return f"❌ Error detecting duplicates: {str(e)}"

# ========================================
# Tool: Merge Memories
# ========================================

async def merge_memories(
    memory_keys: list[str],
    merged_content: str = None,
    keep_all_tags: bool = True,
    delete_originals: bool = True
) -> str:
    """
    Merge multiple memories into a single consolidated memory.
    
    This tool combines multiple related or duplicate memories into one,
    preserving important information while reducing clutter.
    
    Args:
        memory_keys: List of memory keys to merge (minimum 2, format: memory_YYYYMMDDHHMMSS)
        merged_content: Content for the merged memory. If None, contents are concatenated with newlines.
        keep_all_tags: If True, combine tags from all memories. If False, use tags from first memory only.
        delete_originals: If True, delete original memories after merge. If False, keep them.
        
    Returns:
        Success message with the new merged memory key, or error message
    """
    try:
        persona = get_current_persona()
        
        # Validate input
        if not memory_keys or len(memory_keys) < 2:
            return "❌ Please provide at least 2 memory keys to merge"
        
        if len(memory_keys) > 10:
            return "❌ Cannot merge more than 10 memories at once"
        
        for key in memory_keys:
            if not key.startswith("memory_"):
                return f"❌ Invalid memory key format: {key}"
        
        # Fetch all memories
        db_path = get_db_path()
        memories = []
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for key in memory_keys:
                cursor.execute(
                    "SELECT content, created_at, tags FROM memories WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if not row:
                    return f"❌ Memory not found: {key}"
                memories.append({
                    "key": key,
                    "content": row[0],
                    "created_at": row[1],
                    "tags": json.loads(row[2]) if row[2] else []
                })
        
        # Sort by timestamp (oldest first)
        memories.sort(key=lambda x: x["created_at"])
        oldest_timestamp = memories[0]["created_at"]
        
        # Merge content
        if merged_content is None:
            # Auto-merge: concatenate with separators
            merged_content = "\n\n".join([m["content"] for m in memories])
        
        # Merge tags
        if keep_all_tags:
            all_tags = set()
            for m in memories:
                all_tags.update(m["tags"])
            merged_tags = list(all_tags)
        else:
            merged_tags = memories[0]["tags"]
        
        # Create merged memory with oldest timestamp
        merged_key = f"memory_{datetime.fromisoformat(oldest_timestamp).strftime('%Y%m%d%H%M%S')}_merged"
        
        # Save to database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO memories 
                   (key, content, created_at, updated_at, tags) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    merged_key,
                    merged_content,
                    oldest_timestamp,
                    get_current_time().isoformat(),
                    json.dumps(merged_tags) if merged_tags else None
                )
            )
            conn.commit()
        
        # Update vector store
        mark_vector_store_dirty()
        
        # Delete originals if requested
        deleted_keys = []
        if delete_originals:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                for key in memory_keys:
                    cursor.execute("DELETE FROM memories WHERE key = ?", (key,))
                    deleted_keys.append(key)
                conn.commit()
        
        # Format result
        result = f"✅ Successfully merged {len(memory_keys)} memories!\n\n"
        result += f"🆕 New merged memory: [{merged_key}]\n"
        result += f"📅 Timestamp: {oldest_timestamp} (oldest)\n"
        result += f"📝 Content ({len(merged_content)} chars):\n"
        result += f"   {merged_content[:200]}{'...' if len(merged_content) > 200 else ''}\n\n"
        
        if merged_tags:
            result += f"🏷️  Tags: {', '.join(merged_tags)}\n\n"
        
        if delete_originals:
            result += f"🗑️  Deleted {len(deleted_keys)} original memories:\n"
            for key in deleted_keys:
                result += f"   - {key}\n"
        else:
            result += f"💡 Original memories kept (delete_originals=False)\n"
        
        result += f"\n💡 Persona: {persona}"
        
        _log_progress(f"✅ Merged {len(memory_keys)} memories into {merged_key}")
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to merge memories: {e}")
        return f"❌ Error merging memories: {str(e)}"

# ========================================
# Resource: Memory Info
# ========================================

def get_memory_info() -> str:
    """Provide memory service info (DB-source of truth)"""
    entries = db_count_entries()
    total_chars = db_sum_content_chars()
    vector_count = get_vector_count()
    db_path = get_db_path()
    persona = get_current_persona()
    cfg = _get_rebuild_config()
    return (
        f"User Memory System Info:\n"
        f"- Entries: {entries}\n"
        f"- Total chars: {total_chars}\n"
        f"- Vector Store: {vector_count} documents\n"
        f"- Reranker: {'Available' if _reranker else 'Not available'}\n"
        f"- Database: {db_path}\n"
        f"- Persona: {persona}\n"
        f"- Vector Rebuild: mode={cfg.get('mode')}, idle_seconds={cfg.get('idle_seconds')}, min_interval={cfg.get('min_interval')}\n"
        f"- Tools: create_memory, read_memory, update_memory, delete_memory, list_memory, search_memory, search_memory_rag, search_memory_by_date, clean_memory\n"
        f"- Key format: memory_YYYYMMDDHHMMSS\n"
        f"- Save format: 'User is ...'\n"
    )

# ========================================
# Resource: Memory Metrics
# ========================================

def get_memory_metrics() -> str:
    """
    Provide detailed metrics for monitoring and debugging.
    
    Returns:
        Formatted string with:
        - Embeddings model name and load status
        - Reranker model name and load status
        - Vector store document count
        - Dirty status (rebuild pending)
        - Last write/rebuild timestamps
        - Rebuild configuration
    """
    from datetime import datetime
    
    metrics = get_vector_metrics()
    persona = get_current_persona()
    
    # Format timestamps
    def format_ts(ts: float) -> str:
        if ts > 0:
            return datetime.fromtimestamp(ts).isoformat()
        return "Never"
    
    last_write = format_ts(metrics["last_write_ts"])
    last_rebuild = format_ts(metrics["last_rebuild_ts"])
    
    rebuild_cfg = metrics["rebuild_config"]
    
    return (
        f"📊 Memory Metrics (persona: {persona}):\n"
        f"\n"
        f"🧠 Models:\n"
        f"  - Embeddings: {metrics['embeddings_model'] or 'Not loaded'} "
        f"({'✅ Loaded' if metrics['embeddings_loaded'] else '❌ Not loaded'})\n"
        f"  - Reranker: {metrics['reranker_model'] or 'Not loaded'} "
        f"({'✅ Loaded' if metrics['reranker_loaded'] else '❌ Not loaded'})\n"
        f"\n"
        f"📦 Vector Store:\n"
        f"  - Documents: {metrics['vector_count']}\n"
        f"  - Dirty: {'✅ Yes (rebuild pending)' if metrics['dirty'] else '❌ No'}\n"
        f"\n"
        f"⏰ Timestamps:\n"
        f"  - Last Write: {last_write}\n"
        f"  - Last Rebuild: {last_rebuild}\n"
        f"\n"
        f"⚙️  Rebuild Config:\n"
        f"  - Mode: {rebuild_cfg['mode']}\n"
        f"  - Idle Seconds: {rebuild_cfg['idle_seconds']}\n"
        f"  - Min Interval: {rebuild_cfg['min_interval']}\n"
    )

# ========================================
# Resource: Memory Statistics Dashboard
# ========================================

def get_memory_stats() -> str:
    """
    Provide comprehensive memory statistics dashboard.
    
    Returns:
        Formatted string with:
        - Total memory count and date range
        - Tag distribution (with percentages)
        - Emotion distribution (with percentages)
        - Timeline (daily memory counts for last 7 days)
        - Link analysis (most mentioned [[links]])
    """
    import re
    from collections import Counter, defaultdict
    from datetime import datetime, timedelta
    
    db_path = get_db_path()
    persona = get_current_persona()
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # ========== Basic Stats ==========
            cursor.execute("SELECT COUNT(*) FROM memories")
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                return f"📊 Memory Statistics (persona: {persona}):\n\n💡 No memories yet!"
            
            # Get date range
            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM memories")
            min_date_str, max_date_str = cursor.fetchone()
            min_date = datetime.fromisoformat(min_date_str).date()
            max_date = datetime.fromisoformat(max_date_str).date()
            date_range_days = (max_date - min_date).days + 1
            avg_per_day = total_count / date_range_days if date_range_days > 0 else 0
            
            # ========== Tag Distribution ==========
            cursor.execute("SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = Counter()
            for row in cursor.fetchall():
                tags_json = row[0]
                try:
                    tags_list = json.loads(tags_json)
                    tag_counter.update(tags_list)
                except:
                    pass
            
            # ========== Emotion Distribution ==========
            # Load persona context to get emotion history
            context = load_persona_context()
            emotion_history = context.get("emotion_history", [])
            emotion_counter = Counter()
            for entry in emotion_history:
                emotion_type = entry.get("emotion_type")
                if emotion_type:
                    emotion_counter[emotion_type] += 1
            
            # ========== Timeline (last 7 days) ==========
            cursor.execute("SELECT created_at FROM memories")
            date_counter = Counter()
            for row in cursor.fetchall():
                created_at = datetime.fromisoformat(row[0]).date()
                date_counter[created_at] += 1
            
            # Get last 7 days
            today = datetime.now().date()
            timeline = []
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                count = date_counter.get(day, 0)
                timeline.append((day, count))
            
            # ========== Link Analysis ==========
            cursor.execute("SELECT content FROM memories")
            link_counter = Counter()
            link_pattern = re.compile(r'\[\[(.+?)\]\]')
            for row in cursor.fetchall():
                content = row[0]
                matches = link_pattern.findall(content)
                link_counter.update(matches)
            
            # ========== Format Output ==========
            output = f"📊 Memory Statistics Dashboard (persona: {persona})\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Basic stats
            output += f"📦 Total Memories: {total_count}\n"
            output += f"📅 Date Range: {min_date} ~ {max_date} ({date_range_days} days)\n"
            output += f"📈 Average per day: {avg_per_day:.2f} memories\n\n"
            
            # Tag distribution
            if tag_counter:
                output += "🏷️  Tag Distribution:\n"
                for tag, count in tag_counter.most_common(10):
                    percentage = (count / total_count) * 100
                    output += f"  - {tag}: {count} ({percentage:.1f}%)\n"
                output += "\n"
            
            # Emotion distribution
            if emotion_counter:
                output += "😊 Emotion Distribution:\n"
                total_emotions = sum(emotion_counter.values())
                for emotion, count in emotion_counter.most_common(10):
                    percentage = (count / total_emotions) * 100
                    output += f"  - {emotion}: {count} ({percentage:.1f}%)\n"
                output += "\n"
            
            # Timeline
            output += "📆 Timeline (last 7 days):\n"
            max_count = max([count for _, count in timeline]) if timeline else 1
            for day, count in timeline:
                bar_length = int((count / max_count) * 10) if max_count > 0 else 0
                bar = "█" * bar_length
                output += f"  {day}: {bar} {count}\n"
            output += "\n"
            
            # Link analysis
            if link_counter:
                output += "🔗 Link Analysis (top 10):\n"
                top_links = link_counter.most_common(10)
                output += "  Most mentioned: "
                link_strs = [f"[[{link}]]({count})" for link, count in top_links]
                output += ", ".join(link_strs)
                output += "\n"
            
            return output
            
    except Exception as e:
        return f"❌ Error generating statistics: {e}"

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
    # Start idle rebuild worker
    try:
        start_idle_rebuilder_thread()
        print("🧵 Idle rebuild worker started")
    except Exception as e:
        print(f"⚠️  Failed to start idle rebuild worker: {e}")
    # ツール/リソースの登録（デコレータではなく動的登録）
    try:
        import tools_memory
        tools_memory.register_tools(mcp)
        tools_memory.register_resources(mcp)
        print("🧰 Tools and resources registered")
    except Exception as e:
        print(f"⚠️  Failed to register tools/resources: {e}")

    # Run MCP server with streamable-http transport
    mcp.run(transport='streamable-http')