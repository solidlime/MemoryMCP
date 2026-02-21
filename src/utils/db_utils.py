import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Tuple, Dict, Any
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


@contextmanager
def get_db_connection(db_path: str):
    """Context manager that opens a SQLite connection with WAL mode and a
    generous busy timeout for concurrent write safety.

    WAL mode allows concurrent readers alongside one writer without blocking
    reads, which is essential when multiple personas or clients access the
    server simultaneously.  WAL is a persistent DB-level setting; the PRAGMA
    is fast (no-op) after the first call for a given file.

    Usage::

        with get_db_connection(db_path) as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")  # 10 s before SQLITE_BUSY
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# These helpers are kept generic: caller passes db_path

def db_get_entry(db_path: str, key: str) -> Optional[Dict[str, Any]]:
    """Return a dictionary with memory data for a key, or None"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT content, created_at, updated_at, tags, importance, emotion, emotion_intensity, physical_state, mental_state, environment, relationship_status, action_tag, related_keys, summary_ref FROM memories WHERE key = ?', (key,))
        row = cursor.fetchone()
        if row is None:
            return None
        
        # Convert tuple to dictionary
        import json
        tags = json.loads(row[3]) if row[3] else []
        related_keys = json.loads(row[12]) if row[12] else []
        
        return {
            'content': row[0],
            'created_at': row[1],
            'updated_at': row[2],
            'tags': tags,
            'importance': row[4],
            'emotion': row[5],
            'emotion_intensity': row[6],
            'physical_state': row[7],
            'mental_state': row[8],
            'environment': row[9],
            'relationship_status': row[10],
            'action_tag': row[11],
            'related_keys': related_keys,
            'summary_ref': row[13]
        }


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
