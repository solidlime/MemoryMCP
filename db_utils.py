import sqlite3
from typing import Optional, List, Tuple
from cachetools import TTLCache
from threading import Lock

# Cache configuration (Phase 18: Performance Optimization)
# TTL = 300 seconds (5 minutes), maxsize = 100 entries
_query_cache = TTLCache(maxsize=100, ttl=300)
_cache_lock = Lock()

def clear_query_cache():
    """Clear all cached query results. Call this when data changes."""
    with _cache_lock:
        _query_cache.clear()

# These helpers are kept generic: caller passes db_path

def db_get_entry(db_path: str, key: str) -> Optional[Tuple[str, str, str, str, float, str, str, str, str, str, str]]:
    """Return (content, created_at, updated_at, tags_json, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag) for a key, or None"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT content, created_at, updated_at, tags, importance, emotion, physical_state, mental_state, environment, relationship_status, action_tag FROM memories WHERE key = ?', (key,))
        return cursor.fetchone()


def db_recent_keys(db_path: str, limit: int = 5) -> List[str]:
    """Return recent keys list by created_at desc"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT key FROM memories ORDER BY created_at DESC LIMIT ?', (limit,))
        return [r[0] for r in cursor.fetchall()]


def db_count_entries(db_path: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM memories')
        (count,) = cursor.fetchone()
        return int(count)


def db_sum_content_chars(db_path: str) -> int:
    """Return SUM(LENGTH(content)) for quick stats; 0 if table empty"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT SUM(LENGTH(content)) FROM memories')
            (total,) = cursor.fetchone()
            return int(total) if total is not None else 0
        except Exception:
            return 0
