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
import glob
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from mcp.server.fastmcp import FastMCP
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from config_utils import (
    ensure_memory_root,
    get_config,
    get_log_file_path,
    load_config,
)
from db_utils import db_get_entry as _db_get_entry_generic, db_recent_keys as _db_recent_keys_generic, db_count_entries as _db_count_entries_generic, db_sum_content_chars as _db_sum_content_chars_generic, clear_query_cache
from persona_utils import (
    current_persona,
    get_current_persona,
    get_persona_dir,
    get_db_path,
    get_vector_store_path,
    get_persona_context_path,
)
from core import (
    get_current_time,
    parse_date_query,
    calculate_time_diff,
    load_persona_context,
    save_persona_context,
)
from vector_utils import (
    initialize_rag_sync as _initialize_rag_sync,
    add_memory_to_vector_store,
    update_memory_in_vector_store,
    delete_memory_from_vector_store,
    rebuild_vector_store,
    start_idle_rebuilder_thread,
    start_cleanup_worker_thread,
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
MEMORY_ROOT = ensure_memory_root()

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
    _early_config = load_config()
except Exception:
    _early_config = {}

# Initialize MCP server with configured host and port
mcp = FastMCP(
    "Memory Service",
    host=_early_config.get("server_host", "127.0.0.1"),
    port=_early_config.get("server_port", 8000)
)

# Initialize Jinja2 templates for dashboard
templates = Jinja2Templates(directory=os.path.join(SCRIPT_DIR, "templates"))

"""Persona helpers are imported from persona_utils"""

LOG_FILE = get_log_file_path()

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
        
        # Clear query cache (Phase 18: Performance Optimization)
        clear_query_cache()
        
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
        
        # Clear query cache (Phase 18: Performance Optimization)
        clear_query_cache()
        
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
            
            # Clear query cache (Phase 18: Performance Optimization)
            clear_query_cache()
            
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
# Tools: Migration between SQLite and Qdrant (Phase 23)
# ========================================

async def migrate_sqlite_to_qdrant_tool() -> str:
    """
    Upsert all current persona's SQLite memories into Qdrant.
    Use when switching backend to Qdrant or initial bootstrap.
    """
    try:
        from vector_utils import migrate_sqlite_to_qdrant
        persona = get_current_persona()
        n = migrate_sqlite_to_qdrant()
        return f"✅ Migrated {n} memories from SQLite to Qdrant (persona: {persona})"
    except Exception as e:
        return f"❌ Failed to migrate to Qdrant: {str(e)}"

async def migrate_qdrant_to_sqlite_tool(upsert: bool = True) -> str:
    """
    Import all records from Qdrant into SQLite for current persona.
    upsert=True to overwrite, False to keep existing rows.
    """
    try:
        from vector_utils import migrate_qdrant_to_sqlite
        persona = get_current_persona()
        n = migrate_qdrant_to_sqlite(upsert=upsert)
        mode = "upsert" if upsert else "insert-ignore"
        return f"✅ Migrated {n} memories from Qdrant to SQLite (persona: {persona}, mode: {mode})"
    except Exception as e:
        return f"❌ Failed to migrate to SQLite: {str(e)}"

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


# ============================================================================
# Phase 19: AI Assist - Sentiment Analysis
# ============================================================================

async def analyze_sentiment(content: str) -> str:
    """
    Analyze sentiment of text content using AI.
    
    Args:
        content: Text content to analyze for sentiment/emotion
        
    Returns:
        Formatted string with detected emotion, confidence score, and details
    """
    try:
        from vector_utils import analyze_sentiment_text
        
        _log_progress(f"🔍 Analyzing sentiment for text ({len(content)} chars)...")
        
        result = analyze_sentiment_text(content)
        
        if "error" in result:
            return f"❌ Error analyzing sentiment: {result.get('error', 'Unknown error')}"
        
        emotion = result.get("emotion", "neutral")
        score = result.get("score", 0.0)
        raw_label = result.get("raw_label", "unknown")
        
        # Format output
        output = "🎭 Sentiment Analysis Result:\n\n"
        output += f"📊 Detected Emotion: **{emotion}** (confidence: {score:.2%})\n"
        output += f"🏷️  Raw Label: {raw_label}\n\n"
        
        # Add emoji based on emotion
        emotion_emoji = {
            "joy": "😊",
            "sadness": "😢",
            "neutral": "😐",
            "anger": "😠",
            "fear": "😨",
            "surprise": "😲",
            "disgust": "😖"
        }
        emoji = emotion_emoji.get(emotion, "🤔")
        
        output += f"{emoji} Interpretation:\n"
        if emotion == "joy":
            output += "   The text expresses positive emotions, happiness, or satisfaction.\n"
        elif emotion == "sadness":
            output += "   The text expresses negative emotions, disappointment, or concern.\n"
        else:
            output += "   The text has a neutral or balanced emotional tone.\n"
        
        output += f"\n💡 Analyzed text ({len(content)} chars):\n"
        output += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n"
        
        _log_progress(f"✅ Sentiment analysis complete: {emotion} ({score:.2%})")
        return output
        
    except Exception as e:
        _log_progress(f"❌ Sentiment analysis failed: {e}")
        return f"❌ Error analyzing sentiment: {str(e)}"


# ============================================================================
# Phase 20: Knowledge Graph Generation
# ============================================================================

async def generate_knowledge_graph(
    format: str = "json",
    min_count: int = 2,
    min_cooccurrence: int = 1,
    remove_isolated: bool = True
) -> str:
    """
    Generate knowledge graph from memory [[links]].
    
    Args:
        format: Output format ('json' or 'html')
        min_count: Minimum link occurrence count (default: 2)
        min_cooccurrence: Minimum co-occurrence count for edges (default: 1)
        remove_isolated: Remove nodes with no connections (default: True)
        
    Returns:
        JSON string or HTML file path
    """
    try:
        from analysis_utils import build_knowledge_graph, export_graph_json, export_graph_html
        from persona_utils import get_current_persona
        
        persona = get_current_persona()
        _log_progress(f"🔍 Generating knowledge graph for persona: {persona}...")
        
        # Build graph
        G = build_knowledge_graph(
            min_count=min_count,
            min_cooccurrence=min_cooccurrence,
            remove_isolated=remove_isolated,
            persona=persona
        )
        
        if G.number_of_nodes() == 0:
            return "⚠️ No links found matching the criteria. Try lowering min_count parameter."
        
        # Export based on format
        if format.lower() == "html":
            # Generate HTML file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"output/knowledge_graph_{persona}_{timestamp}.html"
            
            file_path = export_graph_html(G, output_path, title=f"Knowledge Graph - {persona}")
            
            result = f"✅ Knowledge graph generated!\n\n"
            result += f"📊 Statistics:\n"
            result += f"   - Total nodes (links): {G.number_of_nodes()}\n"
            result += f"   - Total edges (connections): {G.number_of_edges()}\n"
            result += f"   - Average connections per node: {sum(dict(G.degree()).values()) / G.number_of_nodes():.2f}\n\n"
            result += f"📁 HTML file saved to: {file_path}\n"
            result += f"💡 Open this file in a web browser to explore the interactive graph!\n"
            
            _log_progress(f"✅ Knowledge graph HTML saved: {file_path}")
            return result
            
        else:  # JSON format
            json_data = export_graph_json(G)
            
            result = f"✅ Knowledge graph generated (JSON format)!\n\n"
            result += f"📊 Statistics:\n"
            result += f"   - Total nodes (links): {G.number_of_nodes()}\n"
            result += f"   - Total edges (connections): {G.number_of_edges()}\n\n"
            result += f"📋 JSON Data:\n"
            result += json_data
            
            _log_progress(f"✅ Knowledge graph JSON generated: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            return result
        
    except Exception as e:
        _log_progress(f"❌ Knowledge graph generation failed: {e}")
        return f"❌ Error generating knowledge graph: {str(e)}"


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

# ========================================
# Phase 22: Web Dashboard HTTP API
# ========================================

def _get_memory_info_data(persona: str) -> dict:
    """Core function to get memory info data for a specific persona."""
    # Temporarily override persona context
    original_persona = current_persona.get()
    current_persona.set(persona)
    
    try:
        entries = db_count_entries()
        total_chars = db_sum_content_chars()
        vector_count = get_vector_count()
        
        # Load persona context
        context = load_persona_context()
        
        # Get database created date
        db_path = get_db_path()
        if os.path.exists(db_path):
            created_at = datetime.fromtimestamp(os.path.getctime(db_path)).isoformat()
        else:
            created_at = "Unknown"
        
        # Get last conversation time
        last_conv = context.get("last_conversation_time")
        if last_conv:
            last_conversation = calculate_time_diff(last_conv)
        else:
            last_conversation = "Never"
        
        return {
            "persona": persona,
            "total_memories": entries,
            "total_chars": total_chars,
            "vector_count": vector_count,
            "created_at": created_at,
            "last_conversation": last_conversation,
            "current_emotion": context.get("current_emotion", "neutral"),
            "physical_state": context.get("physical_state", "normal"),
            "mental_state": context.get("mental_state", "calm"),
            "environment": context.get("environment", "unknown")
        }
    finally:
        current_persona.set(original_persona)

def _get_memory_metrics_data(persona: str) -> dict:
    """Core function to get memory metrics data for a specific persona."""
    original_persona = current_persona.get()
    current_persona.set(persona)
    
    try:
        import re
        from collections import Counter
        
        db_path = get_db_path()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Tag distribution
            cursor.execute("SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = Counter()
            for row in cursor.fetchall():
                tags_json = row[0]
                try:
                    tags_list = json.loads(tags_json)
                    tag_counter.update(tags_list)
                except:
                    pass
            
            # Emotion distribution
            context = load_persona_context()
            emotion_history = context.get("emotion_history", [])
            emotion_counter = Counter()
            for entry in emotion_history:
                emotion_type = entry.get("emotion_type")
                if emotion_type:
                    emotion_counter[emotion_type] += 1
            
            # Tagged/Linked memory counts
            cursor.execute("SELECT COUNT(*) FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tagged_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT content FROM memories")
            link_pattern = re.compile(r'\[\[(.+?)\]\]')
            linked_count = 0
            for row in cursor.fetchall():
                if link_pattern.search(row[0]):
                    linked_count += 1
            
            return {
                "persona": persona,
                "top_tags": dict(tag_counter.most_common(10)),
                "emotion_distribution": dict(emotion_counter.most_common(10)),
                "tagged_memories_count": tagged_count,
                "linked_memories_count": linked_count
            }
    finally:
        current_persona.set(original_persona)

def _get_memory_stats_data(persona: str) -> dict:
    """Core function to get memory stats data for a specific persona."""
    original_persona = current_persona.get()
    current_persona.set(persona)
    
    try:
        import re
        from collections import Counter
        
        db_path = get_db_path()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Timeline (last 7 days)
            cursor.execute("SELECT created_at FROM memories")
            date_counter = Counter()
            for row in cursor.fetchall():
                created_at = datetime.fromisoformat(row[0]).date()
                date_counter[created_at] += 1
            
            today = datetime.now().date()
            timeline = []
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                count = date_counter.get(day, 0)
                timeline.append({"date": str(day), "count": count})
            
            # Tag distribution
            cursor.execute("SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = Counter()
            for row in cursor.fetchall():
                tags_json = row[0]
                try:
                    tags_list = json.loads(tags_json)
                    tag_counter.update(tags_list)
                except:
                    pass
            
            # Link analysis
            cursor.execute("SELECT content FROM memories")
            link_counter = Counter()
            link_pattern = re.compile(r'\[\[(.+?)\]\]')
            for row in cursor.fetchall():
                content = row[0]
                matches = link_pattern.findall(content)
                link_counter.update(matches)
            
            return {
                "persona": persona,
                "last_7_days": timeline,
                "tag_distribution": dict(tag_counter.most_common(10)),
                "top_links": dict(link_counter.most_common(10))
            }
    finally:
        current_persona.set(original_persona)

def _get_latest_knowledge_graph(persona: str) -> str:
    """Get the URL of the latest knowledge graph HTML file for a persona."""
    pattern = os.path.join(SCRIPT_DIR, "output", f"knowledge_graph_{persona}_*.html")
    files = glob.glob(pattern)
    if not files:
        return None
    # Return the latest file (based on timestamp in filename)
    latest = max(files)
    # Return relative URL path
    filename = os.path.basename(latest)
    return f"/output/{filename}"

# HTTP Routes for Dashboard
@mcp.custom_route("/", methods=["GET"])
async def dashboard(request: Request):
    """Serve the dashboard HTML page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Simple health endpoint for Docker healthcheck
@mcp.custom_route("/health", methods=["GET"])
async def healthcheck(request: Request):
    """Return 200 OK when server is healthy."""
    try:
        persona = get_current_persona()
    except Exception:
        persona = "unknown"
    return JSONResponse({
        "status": "ok",
        "persona": persona,
        "time": datetime.now().isoformat()
    })

@mcp.custom_route("/api/personas", methods=["GET"])
async def get_personas(request: Request):
    """Get list of available personas."""
    memory_dir = MEMORY_ROOT
    if not os.path.exists(memory_dir):
        return JSONResponse([])
    
    personas = []
    for item in os.listdir(memory_dir):
        item_path = os.path.join(memory_dir, item)
        if os.path.isdir(item_path):
            # Check if it has a valid database
            db_path = os.path.join(item_path, "memory.sqlite")
            if os.path.exists(db_path):
                personas.append(item)
    
    return JSONResponse(personas)

@mcp.custom_route("/api/dashboard/{persona}", methods=["GET"])
async def get_dashboard_data(request: Request):
    """Get dashboard data for a specific persona."""
    persona = request.path_params.get("persona")
    
    # Validate persona exists
    memory_dir = os.path.join(MEMORY_ROOT, persona)
    if not os.path.exists(memory_dir):
        raise HTTPException(status_code=404, detail=f"Persona '{persona}' not found")
    
    try:
        info = _get_memory_info_data(persona)
        metrics = _get_memory_metrics_data(persona)
        stats = _get_memory_stats_data(persona)
        kg_url = _get_latest_knowledge_graph(persona)
        
        return JSONResponse({
            "persona": persona,
            "info": info,
            "metrics": metrics,
            "stats": stats,
            "knowledge_graph_url": kg_url,
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading data: {str(e)}")

@mcp.custom_route("/output/{filename}", methods=["GET"])
async def serve_output_file(request: Request):
    """Serve static files from the output directory."""
    filename = request.path_params.get("filename")
    file_path = os.path.join(SCRIPT_DIR, "output", filename)
    
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=403, detail="Invalid filename")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)

# ========================================
# Resource: Cleanup Suggestions (Phase 21)
# ========================================

def get_cleanup_suggestions() -> str:
    """
    Provide cleanup suggestions generated by idle worker.
    
    Returns:
        Formatted cleanup suggestions with merge commands
    """
    try:
        persona = get_current_persona()
        persona_dir = get_persona_dir(persona)
        suggestions_file = os.path.join(persona_dir, "cleanup_suggestions.json")
        
        if not os.path.exists(suggestions_file):
            return (
                f"🧹 Cleanup Suggestions (persona: {persona})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"No suggestions available yet.\n\n"
                f"💡 Suggestions are generated automatically after 30 minutes of idle time.\n"
                f"   You can also run: detect_duplicates(threshold=0.90)\n"
            )
        
        # Load suggestions
        with open(suggestions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Calculate time since generation
        generated_at = datetime.fromisoformat(data['generated_at'])
        now = datetime.now(generated_at.tzinfo)
        time_diff = now - generated_at
        
        if time_diff.days > 0:
            time_ago = f"{time_diff.days}日前"
        elif time_diff.seconds >= 3600:
            hours = time_diff.seconds // 3600
            time_ago = f"{hours}時間前"
        elif time_diff.seconds >= 60:
            minutes = time_diff.seconds // 60
            time_ago = f"{minutes}分前"
        else:
            time_ago = "たった今"
        
        # Format output
        output = f"🧹 Cleanup Suggestions (persona: {data['persona']})\n"
        output += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"Generated: {time_ago}\n"
        output += f"Total memories: {data['total_memories']}\n\n"
        
        summary = data['summary']
        if summary['total_groups'] == 0:
            output += "✅ No duplicate or similar memories found.\n"
            output += "   Your memory is well organized!\n"
            return output
        
        # Group by priority
        high_priority = [g for g in data['groups'] if g['priority'] == 'high']
        medium_priority = [g for g in data['groups'] if g['priority'] == 'medium']
        low_priority = [g for g in data['groups'] if g['priority'] == 'low']
        
        # High priority
        if high_priority:
            output += f"━━━ 🔴 High Priority ({len(high_priority)} groups) ━━━\n"
            output += "Almost identical - strongly recommend merging\n\n"
            for group in high_priority[:5]:  # Show top 5
                output += f"Group {group['group_id']}: {len(group['memory_keys'])} memories ({group['similarity']*100:.1f}% similar)\n"
                for key in group['memory_keys']:
                    output += f"  📝 {key}\n"
                output += f"  Preview: {group['preview']}\n"
                output += f"  💡 Run: merge_memories({json.dumps(group['memory_keys'])})\n\n"
        
        # Medium priority
        if medium_priority:
            output += f"━━━ 🟡 Medium Priority ({len(medium_priority)} groups) ━━━\n"
            output += "Very similar - consider merging\n\n"
            for group in medium_priority[:3]:  # Show top 3
                output += f"Group {group['group_id']}: {len(group['memory_keys'])} memories ({group['similarity']*100:.1f}% similar)\n"
                for key in group['memory_keys']:
                    output += f"  📝 {key}\n"
                output += f"  💡 Review: read_memory('{group['memory_keys'][0]}')\n\n"
        
        # Low priority
        if low_priority:
            output += f"━━━ 🟢 Low Priority ({len(low_priority)} groups) ━━━\n"
            output += "Somewhat similar - may be related\n"
            output += f"  {len(low_priority)} groups found (not shown for brevity)\n\n"
        
        # Summary
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"📊 Summary:\n"
        output += f"  - Total groups: {summary['total_groups']}\n"
        output += f"  - High priority: {summary['high_priority']}\n"
        output += f"  - Medium priority: {summary['medium_priority']}\n"
        output += f"  - Low priority: {summary['low_priority']}\n\n"
        output += "💡 Next cleanup check will run automatically after idle time.\n"
        
        return output
        
    except Exception as e:
        return f"❌ Error loading cleanup suggestions: {e}"

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
    
    # Phase 21: Start cleanup worker
    try:
        start_cleanup_worker_thread()
        print("🧹 Cleanup worker started")
    except Exception as e:
        print(f"⚠️  Failed to start cleanup worker: {e}")
    
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