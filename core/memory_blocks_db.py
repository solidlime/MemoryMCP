"""
Named memory blocks for memory-mcp (Letta/MemGPT-inspired).

Memory blocks are structured, always-in-context "RAM" segments.
Unlike regular memories (which are retrieved by search), blocks are
always surfaced in get_context() and can be directly read/written.

Standard blocks:
  persona_state  - Herta's current internal state, mood, ongoing goals
  user_model     - What Herta knows/infers about the user (beliefs, interests, etc.)
  active_context - Current session focus, open questions, ongoing topics

Usage:
    write_block(persona, "user_model", "らうらうはmemory-mcpを開発中。Python好き。")
    content = read_block(persona, "user_model")
    blocks = list_blocks(persona)
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any
from zoneinfo import ZoneInfo

from src.utils.persona_utils import get_db_path, get_current_persona
from src.utils.config_utils import load_config
from src.utils.logging_utils import log_progress

# Standard block names and their descriptions
STANDARD_BLOCKS: Dict[str, str] = {
    "persona_state": "ペルソナの現在の内部状態・気分・進行中の目標",
    "user_model": "ユーザーについて知っていること・推測（信念・興味・習慣など）",
    "active_context": "現在のセッションのフォーカス・未解決の問い・進行中のトピック",
}


def _now_iso() -> str:
    cfg = load_config()
    tz = cfg.get("timezone", "Asia/Tokyo")
    return datetime.now(ZoneInfo(tz)).isoformat()


def read_block(
    persona: Optional[str],
    name: str,
) -> Optional[str]:
    """
    Read the content of a named memory block.

    Args:
        persona: Persona name (defaults to current)
        name: Block name (e.g. "user_model")

    Returns:
        Block content string, or None if not found
    """
    if persona is None:
        persona = get_current_persona()

    db_path = get_db_path(persona)

    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT content FROM memory_blocks WHERE persona = ? AND name = ?",
                (persona, name),
            ).fetchone()
        return row[0] if row else None
    except Exception as e:
        log_progress(f"❌ read_block failed ({name}): {e}")
        return None


def write_block(
    persona: Optional[str],
    name: str,
    content: str,
    description: Optional[str] = None,
) -> bool:
    """
    Write (upsert) the content of a named memory block.

    Args:
        persona: Persona name (defaults to current)
        name: Block name
        content: Block content (replaces existing)
        description: Optional description override

    Returns:
        True on success
    """
    if persona is None:
        persona = get_current_persona()

    if not name:
        return False

    db_path = get_db_path(persona)
    now = _now_iso()
    desc = description or STANDARD_BLOCKS.get(name)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory_blocks (persona, name, content, description, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(persona, name) DO UPDATE SET
                    content = excluded.content,
                    description = COALESCE(excluded.description, memory_blocks.description),
                    updated_at = excluded.updated_at
                """,
                (persona, name, content, desc, now),
            )
            conn.commit()
        log_progress(f"✅ block written: {name} (persona={persona})")
        return True
    except Exception as e:
        log_progress(f"❌ write_block failed ({name}): {e}")
        return False


def delete_block(
    persona: Optional[str],
    name: str,
) -> bool:
    """Delete a named memory block."""
    if persona is None:
        persona = get_current_persona()

    db_path = get_db_path(persona)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "DELETE FROM memory_blocks WHERE persona = ? AND name = ?",
                (persona, name),
            )
            conn.commit()
        return True
    except Exception as e:
        log_progress(f"❌ delete_block failed ({name}): {e}")
        return False


def list_blocks(
    persona: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all named memory blocks for a persona.

    Returns:
        List of dicts with name, content, description, updated_at
    """
    if persona is None:
        persona = get_current_persona()

    db_path = get_db_path(persona)

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT name, content, description, updated_at
                FROM memory_blocks
                WHERE persona = ?
                ORDER BY name
                """,
                (persona,),
            ).fetchall()
        return [
            {
                "name": r[0],
                "content": r[1],
                "description": r[2],
                "updated_at": r[3],
            }
            for r in rows
        ]
    except Exception as e:
        log_progress(f"❌ list_blocks failed: {e}")
        return []
