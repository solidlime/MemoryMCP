import sqlite3
from typing import Optional, List, Tuple

# These helpers are kept generic: caller passes db_path

def db_get_entry(db_path: str, key: str) -> Optional[Tuple[str, str, str, str]]:
    """Return (content, created_at, updated_at, tags_json) for a key, or None"""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT content, created_at, updated_at, tags FROM memories WHERE key = ?', (key,))
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
