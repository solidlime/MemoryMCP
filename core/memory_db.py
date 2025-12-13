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

from src.utils.persona_utils import get_current_persona, get_db_path
from src.utils.logging_utils import log_progress


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
            cursor.execute("""
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
                    summary_ref TEXT DEFAULT NULL,
                    equipped_items TEXT DEFAULT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT DEFAULT NULL
                )
            """)
            cursor.execute("""
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
            """)
            
            # Phase 40: State history tables for time-series visualization
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS physical_sensations_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    memory_key TEXT,
                    fatigue REAL DEFAULT 0.0,
                    warmth REAL DEFAULT 0.5,
                    arousal REAL DEFAULT 0.0,
                    touch_response TEXT DEFAULT 'normal',
                    heart_rate_metaphor TEXT DEFAULT 'calm',
                    FOREIGN KEY (memory_key) REFERENCES memories(key) ON DELETE SET NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emotion_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    memory_key TEXT,
                    emotion TEXT NOT NULL,
                    emotion_intensity REAL DEFAULT 0.0,
                    FOREIGN KEY (memory_key) REFERENCES memories(key) ON DELETE SET NULL
                )
            """)
            
            # Phase 41: Promises and Goals tables for multiple task management
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS promises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    due_date TEXT,
                    status TEXT DEFAULT 'active',
                    completed_at TEXT,
                    priority INTEGER DEFAULT 0,
                    notes TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    target_date TEXT,
                    status TEXT DEFAULT 'active',
                    completed_at TEXT,
                    progress INTEGER DEFAULT 0,
                    notes TEXT
                )
            """)
            
            conn.commit()
            
            if not os.path.exists(db_path) or os.path.getsize(db_path) < 100:
                print(f"Initialized SQLite database at {db_path}")
                log_progress(f"Initialized SQLite database at {db_path}")
        
        # Load existing data and migrate schema if needed
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check if tags column exists, add if not (migration)
            cursor.execute("PRAGMA table_info(memories)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'tags' not in columns:
                log_progress("🔄 Migrating database: Adding tags column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN tags TEXT')
                conn.commit()
                log_progress("✅ Database migration complete: tags column added")
            
            # Phase 25.5: Add importance and emotion columns
            if 'importance' not in columns:
                log_progress("🔄 Migrating database: Adding importance column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5')
                conn.commit()
                log_progress("✅ Database migration complete: importance column added")
            
            if 'emotion' not in columns:
                log_progress("🔄 Migrating database: Adding emotion column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN emotion TEXT DEFAULT "neutral"')
                conn.commit()
                log_progress("✅ Database migration complete: emotion column added")
            
            # Phase 25.5 Extended: Add context state columns
            if 'physical_state' not in columns:
                log_progress("🔄 Migrating database: Adding physical_state column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN physical_state TEXT DEFAULT "normal"')
                conn.commit()
                log_progress("✅ Database migration complete: physical_state column added")
            
            if 'mental_state' not in columns:
                log_progress("🔄 Migrating database: Adding mental_state column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN mental_state TEXT DEFAULT "calm"')
                conn.commit()
                log_progress("✅ Database migration complete: mental_state column added")
            
            if 'environment' not in columns:
                log_progress("🔄 Migrating database: Adding environment column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN environment TEXT DEFAULT "unknown"')
                conn.commit()
                log_progress("✅ Database migration complete: environment column added")
            
            if 'relationship_status' not in columns:
                log_progress("🔄 Migrating database: Adding relationship_status column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN relationship_status TEXT DEFAULT "normal"')
                conn.commit()
                log_progress("✅ Database migration complete: relationship_status column added")
            
            if 'action_tag' not in columns:
                log_progress("🔄 Migrating database: Adding action_tag column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN action_tag TEXT DEFAULT NULL')
                conn.commit()
                log_progress("✅ Database migration complete: action_tag column added")
            
            # Phase 28.1: Add emotion intensity, related keys, and summary reference columns
            if 'emotion_intensity' not in columns:
                log_progress("🔄 Migrating database: Adding emotion_intensity column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN emotion_intensity REAL DEFAULT 0.0')
                conn.commit()
                log_progress("✅ Database migration complete: emotion_intensity column added")
            
            if 'related_keys' not in columns:
                log_progress("🔄 Migrating database: Adding related_keys column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN related_keys TEXT DEFAULT "[]"')
                conn.commit()
                log_progress("✅ Database migration complete: related_keys column added")
            
            if 'summary_ref' not in columns:
                log_progress("🔄 Migrating database: Adding summary_ref column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN summary_ref TEXT DEFAULT NULL')
                conn.commit()
                log_progress("✅ Database migration complete: summary_ref column added")
            
            if 'equipped_items' not in columns:
                log_progress("🔄 Migrating database: Adding equipped_items column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN equipped_items TEXT DEFAULT NULL')
                conn.commit()
                log_progress("✅ Database migration complete: equipped_items column added")
            
            # Phase 38: Add access tracking columns
            if 'access_count' not in columns:
                log_progress("🔄 Migrating database: Adding access_count column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0')
                conn.commit()
                log_progress("✅ Database migration complete: access_count column added")
            
            if 'last_accessed' not in columns:
                log_progress("🔄 Migrating database: Adding last_accessed column...")
                cursor.execute('ALTER TABLE memories ADD COLUMN last_accessed TEXT DEFAULT NULL')
                conn.commit()
                log_progress("✅ Database migration complete: last_accessed column added")
            
            cursor.execute('SELECT key, content, created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref, equipped_items, access_count, last_accessed FROM memories')
            rows = cursor.fetchall()
            
            for row in rows:
                key, content, created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref, equipped_items_json, access_count, last_accessed = row
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
                    "summary_ref": summary_ref if summary_ref else None,
                    "equipped_items": json.loads(equipped_items_json) if equipped_items_json else None,
                    "access_count": access_count if access_count is not None else 0,
                    "last_accessed": last_accessed if last_accessed else None
                }
        
        print(f"Loaded {len(memory_store)} memory entries from {db_path}")
        log_progress(f"Loaded {len(memory_store)} memory entries from {db_path}")
    except Exception as e:
        print(f"Failed to load memory database: {e}")
        log_progress(f"Failed to load memory database: {e}")
    
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
    summary_ref: Optional[str] = None,
    equipped_items: Optional[Dict[str, str]] = None,
    persona: Optional[str] = None
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
        equipped_items: Optional dict of equipped items {slot: item_name} (defaults to None)
        persona: Persona name (None = use current context)
    
    Returns:
        bool: Success status
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        log_progress(f"💾 Attempting to save to DB: {db_path} (persona: {persona})")
        
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
        # equipped_items remains None if not provided (no default)
        
        # Validate ranges
        importance = max(0.0, min(1.0, importance))
        emotion_intensity = max(0.0, min(1.0, emotion_intensity))
        
        # Serialize tags, related_keys, and equipped_items as JSON
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        related_keys_json = json.dumps(related_keys, ensure_ascii=False)
        equipped_items_json = json.dumps(equipped_items, ensure_ascii=False) if equipped_items else None
        log_progress(f"💾 Tags JSON: {tags_json}, importance: {importance}, emotion: {emotion}, emotion_intensity: {emotion_intensity}, physical: {physical_state}, mental: {mental_state}, env: {environment}, relation: {relationship_status}, action: {action_tag}, related_keys: {related_keys_json}, summary_ref: {summary_ref}, equipped_items: {equipped_items_json}")
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check schema before insert
            cursor.execute("PRAGMA table_info(memories)")
            columns = [col[1] for col in cursor.fetchall()]
            log_progress(f"💾 DB columns: {columns}")
            
            cursor.execute("""
                INSERT OR REPLACE INTO memories (key, content, created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref, equipped_items)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (key, content, created_at, updated_at, tags_json, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys_json, summary_ref, equipped_items_json))
            conn.commit()
            log_progress(f"✅ Successfully saved {key} to DB")
        
        return True
    except Exception as e:
        print(f"Failed to save memory to database: {e}")
        log_progress(f"❌ Failed to save memory to database: {e}")
        log_progress(f"❌ DB path was: {db_path}")
        import traceback
        log_progress(f"❌ Traceback: {traceback.format_exc()}")
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
        log_progress(f"Failed to delete memory from database: {e}")
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
            cursor.execute("""
                INSERT INTO operations 
                (timestamp, operation_id, operation, key, before, after, success, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
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


def increment_access_count(key: str) -> bool:
    """
    Increment access count and update last accessed timestamp.
    
    Args:
        key: Memory key
    
    Returns:
        bool: True if successful
    """
    try:
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            from datetime import datetime
            now = datetime.now().isoformat()
            cursor.execute("""
                UPDATE memories
                SET access_count = access_count + 1,
                    last_accessed = ?
                WHERE key = ?
            """, (now, key))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Failed to increment access count for {key}: {e}")
        return False



def save_physical_sensations_history(
    memory_key: Optional[str],
    fatigue: float = 0.0,
    warmth: float = 0.5,
    arousal: float = 0.0,
    touch_response: str = "normal",
    heart_rate_metaphor: str = "calm",
    timestamp: Optional[str] = None,
    persona: Optional[str] = None
) -> bool:
    """
    Save physical sensations state to history table.
    
    Args:
        memory_key: Associated memory key (optional)
        fatigue: Fatigue level (0.0-1.0)
        warmth: Warmth level (0.0-1.0)
        arousal: Arousal level (0.0-1.0)
        touch_response: Touch response state
        heart_rate_metaphor: Heart rate metaphor
        timestamp: Timestamp (defaults to now)
        persona: Persona name (defaults to current)
    
    Returns:
        bool: Success status
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        # Validate ranges
        fatigue = max(0.0, min(1.0, fatigue))
        warmth = max(0.0, min(1.0, warmth))
        arousal = max(0.0, min(1.0, arousal))
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO physical_sensations_history 
                (timestamp, memory_key, fatigue, warmth, arousal, touch_response, heart_rate_metaphor)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, memory_key, fatigue, warmth, arousal, touch_response, heart_rate_metaphor))
            conn.commit()
        
        return True
    except Exception as e:
        log_progress(f"❌ Failed to save physical sensations history: {e}")
        return False


def save_emotion_history(
    memory_key: Optional[str],
    emotion: str,
    emotion_intensity: float = 0.0,
    timestamp: Optional[str] = None,
    persona: Optional[str] = None
) -> bool:
    """
    Save emotion state to history table.
    
    Args:
        memory_key: Associated memory key (optional)
        emotion: Emotion label
        emotion_intensity: Emotion intensity (0.0-1.0)
        timestamp: Timestamp (defaults to now)
        persona: Persona name (defaults to current)
    
    Returns:
        bool: Success status
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        # Validate range
        emotion_intensity = max(0.0, min(1.0, emotion_intensity))
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO emotion_history 
                (timestamp, memory_key, emotion, emotion_intensity)
                VALUES (?, ?, ?, ?)
            """, (timestamp, memory_key, emotion, emotion_intensity))
            conn.commit()
        
        return True
    except Exception as e:
        log_progress(f"❌ Failed to save emotion history: {e}")
        return False


def get_latest_physical_sensations(persona: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get latest physical sensations state from history table.
    
    Args:
        persona: Persona name (defaults to current)
    
    Returns:
        Dict with physical sensations data, or None if no history
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, fatigue, warmth, arousal, touch_response, heart_rate_metaphor
                FROM physical_sensations_history
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                return {
                    "timestamp": row[0],
                    "fatigue": row[1],
                    "warmth": row[2],
                    "arousal": row[3],
                    "touch_response": row[4],
                    "heart_rate_metaphor": row[5]
                }
            return None
    except Exception as e:
        log_progress(f"❌ Failed to get latest physical sensations: {e}")
        return None


def get_latest_emotion(persona: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get latest emotion state from history table.
    
    Args:
        persona: Persona name (defaults to current)
    
    Returns:
        Dict with emotion data, or None if no history
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, emotion, emotion_intensity
                FROM emotion_history
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                return {
                    "timestamp": row[0],
                    "emotion": row[1],
                    "emotion_intensity": row[2]
                }
            return None
    except Exception as e:
        log_progress(f"❌ Failed to get latest emotion: {e}")
        return None


def get_physical_sensations_timeline(
    days: int = 7,
    persona: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get physical sensations timeline for visualization.
    
    Args:
        days: Number of days to retrieve (default: 7)
        persona: Persona name (defaults to current)
    
    Returns:
        List of physical sensations records
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, fatigue, warmth, arousal, touch_response, heart_rate_metaphor
                FROM physical_sensations_history
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (cutoff,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "timestamp": row[0],
                    "fatigue": row[1],
                    "warmth": row[2],
                    "arousal": row[3],
                    "touch_response": row[4],
                    "heart_rate_metaphor": row[5]
                })
            return results
    except Exception as e:
        log_progress(f"❌ Failed to get physical sensations timeline: {e}")
        return []


def get_emotion_timeline(
    days: int = 7,
    persona: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get emotion timeline for visualization.
    
    Args:
        days: Number of days to retrieve (default: 7)
        persona: Persona name (defaults to current)
    
    Returns:
        List of emotion records
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, emotion, emotion_intensity
                FROM emotion_history
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (cutoff,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "timestamp": row[0],
                    "emotion": row[1],
                    "emotion_intensity": row[2]
                })
            return results
    except Exception as e:
        log_progress(f"❌ Failed to get emotion timeline: {e}")
        return []


def get_anniversaries(persona: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get anniversary memories grouped by month-day for calendar display.
    Returns memories tagged with 'anniversary', 'milestone', or 'first_time' grouped by MM-DD format.
    
    Anniversary tags should be used for:
    - anniversary: Special commemorative dates (first meeting, relationship milestones)
    - milestone: Important achievements or life events
    - first_time: First time experiences worth remembering
    
    Args:
        persona: Persona name (defaults to current)
    
    Returns:
        List of anniversary records with date and associated memories
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    key,
                    content,
                    created_at,
                    importance,
                    emotion,
                    emotion_intensity,
                    tags
                FROM memories
                WHERE tags LIKE '%anniversary%' 
                   OR tags LIKE '%milestone%' 
                   OR tags LIKE '%first_time%'
                ORDER BY created_at DESC
            """)
            
            # Group by month-day
            anniversaries = {}
            for row in cursor.fetchall():
                key, content, created_at, importance, emotion, emotion_intensity, tags_json = row
                
                # Extract month-day from created_at (YYYY-MM-DD format)
                date_obj = datetime.fromisoformat(created_at)
                month_day = date_obj.strftime("%m-%d")  # "MM-DD"
                year = date_obj.year
                
                # Parse tags
                tags = json.loads(tags_json) if tags_json else []
                
                # Create short preview (first 100 chars)
                preview = content[:100] + "..." if len(content) > 100 else content
                
                if month_day not in anniversaries:
                    anniversaries[month_day] = []
                
                anniversaries[month_day].append({
                    "key": key,
                    "year": year,
                    "date": created_at[:10],  # "YYYY-MM-DD"
                    "preview": preview,
                    "importance": importance,
                    "emotion": emotion,
                    "emotion_intensity": emotion_intensity,
                    "tags": tags
                })
            
            # Convert to list format for API
            result = []
            for month_day, memories in sorted(anniversaries.items()):
                result.append({
                    "month_day": month_day,  # "MM-DD"
                    "count": len(memories),
                    "memories": memories
                })
            
            return result
    except Exception as e:
        log_progress(f"❌ Failed to get anniversaries: {e}")
        return []


# ===== Phase 41: Promises and Goals Management =====

def save_promise(content: str, due_date: str = None, priority: int = 0, notes: str = None, persona: str = None) -> int:
    """
    Save a new promise to database.
    
    Args:
        content: Promise content
        due_date: Optional due date (ISO format)
        priority: Priority level (default 0)
        notes: Optional notes
        persona: Persona name (defaults to current)
    
    Returns:
        Promise ID
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config
        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))).isoformat()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO promises (content, created_at, due_date, priority, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (content, now, due_date, priority, notes))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        log_progress(f"❌ Failed to save promise: {e}")
        return -1


def get_promises(status: str = 'active', persona: str = None) -> list:
    """
    Get promises from database.
    
    Args:
        status: Filter by status ('active', 'completed', 'cancelled', or 'all')
        persona: Persona name (defaults to current)
    
    Returns:
        List of promise dicts
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            if status == 'all':
                cursor.execute("""
                    SELECT id, content, created_at, due_date, status, completed_at, priority, notes
                    FROM promises
                    ORDER BY priority DESC, created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT id, content, created_at, due_date, status, completed_at, priority, notes
                    FROM promises
                    WHERE status = ?
                    ORDER BY priority DESC, created_at DESC
                """, (status,))
            
            promises = []
            for row in cursor.fetchall():
                promises.append({
                    'id': row[0],
                    'content': row[1],
                    'created_at': row[2],
                    'due_date': row[3],
                    'status': row[4],
                    'completed_at': row[5],
                    'priority': row[6],
                    'notes': row[7]
                })
            return promises
    except Exception as e:
        log_progress(f"❌ Failed to get promises: {e}")
        return []


def update_promise_status(promise_id: int, status: str, persona: str = None) -> bool:
    """
    Update promise status.
    
    Args:
        promise_id: Promise ID
        status: New status ('active', 'completed', 'cancelled')
        persona: Persona name (defaults to current)
    
    Returns:
        Success boolean
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config
        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))).isoformat()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            if status == 'completed':
                cursor.execute("""
                    UPDATE promises
                    SET status = ?, completed_at = ?
                    WHERE id = ?
                """, (status, now, promise_id))
            else:
                cursor.execute("""
                    UPDATE promises
                    SET status = ?, completed_at = NULL
                    WHERE id = ?
                """, (status, promise_id))
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        log_progress(f"❌ Failed to update promise status: {e}")
        return False


def save_goal(content: str, target_date: str = None, progress: int = 0, notes: str = None, persona: str = None) -> int:
    """
    Save a new goal to database.
    
    Args:
        content: Goal content
        target_date: Optional target date (ISO format)
        progress: Progress percentage 0-100 (default 0)
        notes: Optional notes
        persona: Persona name (defaults to current)
    
    Returns:
        Goal ID
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config
        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))).isoformat()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO goals (content, created_at, target_date, progress, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (content, now, target_date, progress, notes))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        log_progress(f"❌ Failed to save goal: {e}")
        return -1


def get_goals(status: str = 'active', persona: str = None) -> list:
    """
    Get goals from database.
    
    Args:
        status: Filter by status ('active', 'completed', 'cancelled', or 'all')
        persona: Persona name (defaults to current)
    
    Returns:
        List of goal dicts
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            if status == 'all':
                cursor.execute("""
                    SELECT id, content, created_at, target_date, status, completed_at, progress, notes
                    FROM goals
                    ORDER BY progress ASC, created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT id, content, created_at, target_date, status, completed_at, progress, notes
                    FROM goals
                    WHERE status = ?
                    ORDER BY progress ASC, created_at DESC
                """, (status,))
            
            goals = []
            for row in cursor.fetchall():
                goals.append({
                    'id': row[0],
                    'content': row[1],
                    'created_at': row[2],
                    'target_date': row[3],
                    'status': row[4],
                    'completed_at': row[5],
                    'progress': row[6],
                    'notes': row[7]
                })
            return goals
    except Exception as e:
        log_progress(f"❌ Failed to get goals: {e}")
        return []


def update_goal_progress(goal_id: int, progress: int, persona: str = None) -> bool:
    """
    Update goal progress.
    
    Args:
        goal_id: Goal ID
        progress: Progress percentage 0-100
        persona: Persona name (defaults to current)
    
    Returns:
        Success boolean
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config
        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))).isoformat()
        
        # Auto-complete if progress reaches 100
        status = 'completed' if progress >= 100 else 'active'
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            if status == 'completed':
                cursor.execute("""
                    UPDATE goals
                    SET progress = ?, status = ?, completed_at = ?
                    WHERE id = ?
                """, (progress, status, now, goal_id))
            else:
                cursor.execute("""
                    UPDATE goals
                    SET progress = ?, status = ?
                    WHERE id = ?
                """, (progress, status, goal_id))
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        log_progress(f"❌ Failed to update goal progress: {e}")
        return False


def get_emotion_history_from_db(limit: int = 10, persona: str = None) -> list:
    """
    Get emotion history from database.
    
    Args:
        limit: Number of recent entries to return
        persona: Persona name (defaults to current)
    
    Returns:
        List of emotion history entries
    """
    try:
        if persona is None:
            persona = get_current_persona()
        db_path = get_db_path(persona)
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, emotion, emotion_intensity, memory_key
                FROM emotion_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'emotion': row[1],
                    'emotion_intensity': row[2],
                    'memory_key': row[3]
                })
            return history
    except Exception as e:
        log_progress(f"❌ Failed to get emotion history: {e}")
        return []
