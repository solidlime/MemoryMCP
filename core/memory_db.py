"""
Memory database operations for memory-mcp.

This module handles SQLite database operations for memory storage.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from persona_utils import get_current_persona, get_db_path


def _log_progress(message: str) -> None:
    """Internal logging function."""
    print(message, flush=True)


def load_memory_from_db() -> Dict[str, Any]:
    """
    Load memory data from SQLite database (persona-scoped).
    
    Returns:
        dict: Memory store with all entries
    """
    memory_store = {}
    try:
        db_path = get_db_path()
        
        # Always ensure tables exist (handles both new and empty databases)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tags TEXT,
                    importance REAL DEFAULT 0.5,
                    emotion TEXT DEFAULT 'neutral',
                    emotion_intensity REAL DEFAULT 0.0,
                    physical_state TEXT DEFAULT 'normal',
                    mental_state TEXT DEFAULT 'calm',
                    environment TEXT DEFAULT 'unknown',
                    relationship_status TEXT DEFAULT 'normal',
                    action_tag TEXT DEFAULT NULL,
                    related_keys TEXT DEFAULT '[]',
                    summary_ref TEXT DEFAULT NULL
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
            
            if not os.path.exists(db_path) or os.path.getsize(db_path) < 100:
                print(f"Initialized SQLite database at {db_path}")
                _log_progress(f"Initialized SQLite database at {db_path}")
        
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
            
            # Phase 25.5: Add importance and emotion columns
            if 'importance' not in columns:
                _log_progress("🔄 Migrating database: Adding importance column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5')
                conn.commit()
                _log_progress("✅ Database migration complete: importance column added")
            
            if 'emotion' not in columns:
                _log_progress("🔄 Migrating database: Adding emotion column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN emotion TEXT DEFAULT "neutral"')
                conn.commit()
                _log_progress("✅ Database migration complete: emotion column added")
            
            # Phase 25.5 Extended: Add context state columns
            if 'physical_state' not in columns:
                _log_progress("🔄 Migrating database: Adding physical_state column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN physical_state TEXT DEFAULT "normal"')
                conn.commit()
                _log_progress("✅ Database migration complete: physical_state column added")
            
            if 'mental_state' not in columns:
                _log_progress("🔄 Migrating database: Adding mental_state column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN mental_state TEXT DEFAULT "calm"')
                conn.commit()
                _log_progress("✅ Database migration complete: mental_state column added")
            
            if 'environment' not in columns:
                _log_progress("🔄 Migrating database: Adding environment column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN environment TEXT DEFAULT "unknown"')
                conn.commit()
                _log_progress("✅ Database migration complete: environment column added")
            
            if 'relationship_status' not in columns:
                _log_progress("🔄 Migrating database: Adding relationship_status column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN relationship_status TEXT DEFAULT "normal"')
                conn.commit()
                _log_progress("✅ Database migration complete: relationship_status column added")
            
            if 'action_tag' not in columns:
                _log_progress("🔄 Migrating database: Adding action_tag column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN action_tag TEXT DEFAULT NULL')
                conn.commit()
                _log_progress("✅ Database migration complete: action_tag column added")
            
            # Phase 28.1: Add emotion intensity, related keys, and summary reference columns
            if 'emotion_intensity' not in columns:
                _log_progress("🔄 Migrating database: Adding emotion_intensity column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN emotion_intensity REAL DEFAULT 0.0')
                conn.commit()
                _log_progress("✅ Database migration complete: emotion_intensity column added")
            
            if 'related_keys' not in columns:
                _log_progress("🔄 Migrating database: Adding related_keys column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN related_keys TEXT DEFAULT "[]"')
                conn.commit()
                _log_progress("✅ Database migration complete: related_keys column added")
            
            if 'summary_ref' not in columns:
                _log_progress("🔄 Migrating database: Adding summary_ref column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN summary_ref TEXT DEFAULT NULL')
                conn.commit()
                _log_progress("✅ Database migration complete: summary_ref column added")
            
            cursor.execute('SELECT key, content, created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref FROM memories')
            rows = cursor.fetchall()
            
            for row in rows:
                key, content, created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref = row
                memory_store[key] = {
                    "content": content,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "tags": json.loads(tags_json) if tags_json else [],
                    "importance": importance if importance is not None else 0.5,
                    "emotion": emotion if emotion else "neutral",
                    "emotion_intensity": emotion_intensity if emotion_intensity is not None else 0.0,
                    "physical_state": physical_state if physical_state else "normal",
                    "mental_state": mental_state if mental_state else "calm",
                    "environment": environment if environment else "unknown",
                    "relationship_status": relationship_status if relationship_status else "normal",
                    "action_tag": action_tag if action_tag else None,
                    "related_keys": json.loads(related_keys_json) if related_keys_json else [],
                    "summary_ref": summary_ref if summary_ref else None
                }
        
        print(f"Loaded {len(memory_store)} memory entries from {db_path}")
        _log_progress(f"Loaded {len(memory_store)} memory entries from {db_path}")
    except Exception as e:
        print(f"Failed to load memory database: {e}")
        _log_progress(f"Failed to load memory database: {e}")
    
    return memory_store


def save_memory_to_db(
    key: str, 
    content: str, 
    created_at: Optional[str] = None, 
    updated_at: Optional[str] = None, 
    tags: Optional[List[str]] = None,
    importance: Optional[float] = None,
    emotion: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    environment: Optional[str] = None,
    relationship_status: Optional[str] = None,
    action_tag: Optional[str] = None,
    related_keys: Optional[List[str]] = None,
    summary_ref: Optional[str] = None
) -> bool:
    """
    Save memory to SQLite database (persona-scoped).
    
    Args:
        key: Memory key
        content: Memory content
        created_at: Creation timestamp (defaults to now)
        updated_at: Update timestamp (defaults to now)
        tags: Optional list of tags
        importance: Optional importance score (0.0-1.0, defaults to 0.5)
        emotion: Optional emotion label (defaults to 'neutral')
        emotion_intensity: Optional emotion intensity (0.0-1.0, defaults to 0.0)
        physical_state: Optional physical state (defaults to 'normal')
        mental_state: Optional mental state (defaults to 'calm')
        environment: Optional environment (defaults to 'unknown')
        relationship_status: Optional relationship status (defaults to 'normal')
        action_tag: Optional action tag (e.g., 'cooking', 'coding', 'kissing', 'walking', etc.)
        related_keys: Optional list of related memory keys (defaults to [])
        summary_ref: Optional reference to summary node (defaults to None)
    
    Returns:
        bool: Success status
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        _log_progress(f"💾 Attempting to save to DB: {db_path} (persona: {persona})")
        
        now = datetime.now().isoformat()
        
        if created_at is None:
            created_at = now
        if updated_at is None:
            updated_at = now
        
        # Defaults for new fields
        if importance is None:
            importance = 0.5
        if emotion is None:
            emotion = "neutral"
        if emotion_intensity is None:
            emotion_intensity = 0.0
        if physical_state is None:
            physical_state = "normal"
        if mental_state is None:
            mental_state = "calm"
        if environment is None:
            environment = "unknown"
        if relationship_status is None:
            relationship_status = "normal"
        # action_tag remains None if not provided (no default)
        if related_keys is None:
            related_keys = []
        # summary_ref remains None if not provided (no default)
        
        # Validate ranges
        importance = max(0.0, min(1.0, importance))
        emotion_intensity = max(0.0, min(1.0, emotion_intensity))
        
        # Serialize tags and related_keys as JSON
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        related_keys_json = json.dumps(related_keys, ensure_ascii=False)
        _log_progress(f"💾 Tags JSON: {tags_json}, importance: {importance}, emotion: {emotion}, emotion_intensity: {emotion_intensity}, physical: {physical_state}, mental: {mental_state}, env: {environment}, relation: {relationship_status}, action: {action_tag}, related_keys: {related_keys_json}, summary_ref: {summary_ref}")
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check schema before insert
            cursor.execute("PRAGMA table_info(memories)")
            columns = [col[1] for col in cursor.fetchall()]
            _log_progress(f"💾 DB columns: {columns}")
            
            cursor.execute('''
                INSERT OR REPLACE INTO memories (key, content, created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (key, content, created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref))
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


def delete_memory_from_db(key: str) -> bool:
    """
    Delete memory from SQLite database (persona-scoped).
    
    Args:
        key: Memory key to delete
    
    Returns:
        bool: Success status
    """
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


def create_memory_entry(content: str) -> Dict[str, str]:
    """
    Create memory entry with metadata.
    
    Args:
        content: Memory content
    
    Returns:
        dict: Memory entry with content, created_at, updated_at
    """
    now = datetime.now().isoformat()
    return {
        "content": content,
        "created_at": now,
        "updated_at": now
    }


def generate_auto_key() -> str:
    """
    Generate auto key from current time.
    
    Returns:
        str: Memory key in format memory_YYYYMMDDHHMMSS
    """
    now = datetime.now()
    return f"memory_{now.strftime('%Y%m%d%H%M%S')}"


def log_operation(
    operation: str, 
    key: Optional[str] = None, 
    before: Optional[Dict] = None, 
    after: Optional[Dict] = None, 
    success: bool = True, 
    error: Optional[str] = None, 
    metadata: Optional[Dict] = None
) -> None:
    """
    Log memory operations to operations table.
    
    Args:
        operation: Operation type (create, read, update, delete, etc.)
        key: Memory key involved
        before: State before operation
        after: State after operation
        success: Whether operation succeeded
        error: Error message if failed
        metadata: Additional metadata
    """
    try:
        db_path = get_db_path()
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation_id": str(uuid.uuid4()),
            "operation": operation,
            "key": key,
            "before": json.dumps(before, ensure_ascii=False) if before else None,
            "after": json.dumps(after, ensure_ascii=False) if after else None,
            "success": 1 if success else 0,
            "error": error,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False)
        }
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO operations 
                (timestamp, operation_id, operation, key, before, after, success, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_entry["timestamp"],
                log_entry["operation_id"],
                log_entry["operation"],
                log_entry["key"],
                log_entry["before"],
                log_entry["after"],
                log_entry["success"],
                log_entry["error"],
                log_entry["metadata"]
            ))
            conn.commit()
    except Exception as e:
        print(f"Failed to log operation: {str(e)}")
