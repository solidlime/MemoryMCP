"""
Bi-temporal user state tracking for memory-mcp.

Instead of overwriting user_info fields, every change is stored with
valid_from / valid_until timestamps. This preserves the full history
of who the user was at any point in time.

Usage:
    update_user_state(persona, "name", "らうらう")
    state = get_current_user_state(persona)   # → {"name": "らうらう", ...}
    history = get_user_state_history(persona, "name")
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any
from zoneinfo import ZoneInfo

from src.utils.persona_utils import get_db_path, get_current_persona
from src.utils.config_utils import load_config
from src.utils.logging_utils import log_progress

# Fields tracked bi-temporally (maps to user_info keys in persona_context.json)
USER_STATE_KEYS = {"name", "nickname", "preferred_address"}


def _now_iso() -> str:
    cfg = load_config()
    tz = cfg.get("timezone", "Asia/Tokyo")
    return datetime.now(ZoneInfo(tz)).isoformat()


def update_user_state(
    persona: Optional[str],
    key: str,
    value: str,
) -> bool:
    """
    Set a new value for a user state key with bi-temporal tracking.

    Marks the currently-valid record as invalid (valid_until = now),
    then inserts a new record with valid_from = now.

    Args:
        persona: Persona name (defaults to current)
        key: State key (e.g. "name", "nickname")
        value: New value

    Returns:
        True on success
    """
    if persona is None:
        persona = get_current_persona()

    db_path = get_db_path(persona)
    now = _now_iso()

    try:
        with sqlite3.connect(db_path) as conn:
            # Invalidate the current record (if any)
            conn.execute(
                """
                UPDATE user_state_history
                SET valid_until = ?
                WHERE persona = ? AND key = ? AND valid_until IS NULL
                """,
                (now, persona, key),
            )
            # Insert the new record
            conn.execute(
                """
                INSERT INTO user_state_history
                    (persona, key, value, valid_from, valid_until, created_at)
                VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (persona, key, value, now, now),
            )
            conn.commit()
        log_progress(f"✅ user_state updated: {key}={value!r} (persona={persona})")
        return True
    except Exception as e:
        log_progress(f"❌ user_state update failed: {e}")
        return False


def update_user_state_bulk(
    persona: Optional[str],
    fields: Dict[str, str],
) -> int:
    """
    Update multiple user state fields at once.

    Args:
        persona: Persona name
        fields: Dict of key → value

    Returns:
        Number of fields updated
    """
    if persona is None:
        persona = get_current_persona()

    updated = 0
    for key, value in fields.items():
        if key in USER_STATE_KEYS and value is not None:
            if update_user_state(persona, key, str(value)):
                updated += 1
    return updated


def get_current_user_state(persona: Optional[str] = None) -> Dict[str, str]:
    """
    Return all currently-valid user state values as a flat dict.

    Args:
        persona: Persona name (defaults to current)

    Returns:
        Dict of key → value for all currently valid records
    """
    if persona is None:
        persona = get_current_persona()

    db_path = get_db_path(persona)

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT key, value FROM user_state_history
                WHERE persona = ? AND valid_until IS NULL
                ORDER BY key
                """,
                (persona,),
            ).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        log_progress(f"❌ get_current_user_state failed: {e}")
        return {}


def get_user_state_history(
    persona: Optional[str] = None,
    key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return full history of user state changes.

    Args:
        persona: Persona name
        key: Specific key to filter (None = all keys)

    Returns:
        List of records with key, value, valid_from, valid_until
    """
    if persona is None:
        persona = get_current_persona()

    db_path = get_db_path(persona)

    try:
        with sqlite3.connect(db_path) as conn:
            if key:
                rows = conn.execute(
                    """
                    SELECT key, value, valid_from, valid_until
                    FROM user_state_history
                    WHERE persona = ? AND key = ?
                    ORDER BY valid_from DESC
                    """,
                    (persona, key),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT key, value, valid_from, valid_until
                    FROM user_state_history
                    WHERE persona = ?
                    ORDER BY key, valid_from DESC
                    """,
                    (persona,),
                ).fetchall()
        return [
            {
                "key": r[0],
                "value": r[1],
                "valid_from": r[2],
                "valid_until": r[3],
                "is_current": r[3] is None,
            }
            for r in rows
        ]
    except Exception as e:
        log_progress(f"❌ get_user_state_history failed: {e}")
        return []
