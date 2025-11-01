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
            print(f"Created new SQLite database at {db_path}")
            _log_progress(f"Created new SQLite database at {db_path}")
            return memory_store
        
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
    
    return memory_store


def save_memory_to_db(
    key: str, 
    content: str, 
    created_at: Optional[str] = None, 
    updated_at: Optional[str] = None, 
    tags: Optional[List[str]] = None
) -> bool:
    """
    Save memory to SQLite database (persona-scoped).
    
    Args:
        key: Memory key
        content: Memory content
        created_at: Creation timestamp (defaults to now)
        updated_at: Update timestamp (defaults to now)
        tags: Optional list of tags
    
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
