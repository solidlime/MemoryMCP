"""
Ebbinghaus Forgetting Curve for Memory MCP.

True Ebbinghaus model:
    R(t) = e^(-t / S)

where:
    R = retention (0.0–1.0)
    t = days since last access
    S = stability (increases each time the memory is recalled)

strength = importance * R(t)

The `importance` column is immutable (set at creation).
The `strength` column in memory_strength table holds the current
effective score used for ranking. It is updated by the background
decay worker and boosted on each recall.

Stability growth on recall:
    S_new = S * STABILITY_GROWTH_FACTOR
    (capped at STABILITY_MAX so a memory can't become immortal)
"""

import math
import sqlite3
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from src.utils.config_utils import load_config
from src.utils.persona_utils import get_db_path
from src.utils.logging_utils import log_progress

# ── Tuning constants ─────────────────────────────────────────────────────────
STABILITY_GROWTH_FACTOR = 1.5   # S multiplier per recall
STABILITY_MAX = 365.0           # caps at ~1 year half-life
STABILITY_EMOTION_BONUS = {     # extra starting stability based on emotion intensity
    "high": 10.0,   # emotion_intensity > 0.7
    "mid": 5.0,     # emotion_intensity > 0.5
    "low": 1.0,     # otherwise
}
DECAY_WORKER_INTERVAL_HOURS = 6  # run decay pass every N hours

_decay_thread: Optional[threading.Thread] = None
_decay_stop_event = threading.Event()


# ── Core Ebbinghaus functions ─────────────────────────────────────────────────

def ebbinghaus_retention(days_since_access: float, stability: float) -> float:
    """
    R(t) = e^(-t / S)

    Args:
        days_since_access: Days elapsed since the memory was last accessed
        stability: Current stability factor (higher = slower decay)

    Returns:
        Retention score 0.0–1.0
    """
    if days_since_access <= 0:
        return 1.0
    s = max(stability, 0.01)
    return math.exp(-days_since_access / s)


def initial_stability(emotion_intensity: float = 0.0) -> float:
    """
    Initial stability based on emotional charge at creation time.

    Emotionally charged memories are harder to forget from the start.
    """
    if emotion_intensity > 0.7:
        return STABILITY_EMOTION_BONUS["high"]
    elif emotion_intensity > 0.5:
        return STABILITY_EMOTION_BONUS["mid"]
    return STABILITY_EMOTION_BONUS["low"]


def compute_strength(importance: float, retention: float) -> float:
    """strength = importance * retention, clamped to [0, 1]."""
    return max(0.0, min(1.0, importance * retention))


# ── Database helpers ──────────────────────────────────────────────────────────

def _now_iso(tz: str = "Asia/Tokyo") -> str:
    return datetime.now(ZoneInfo(tz)).isoformat()


def _days_since(ts: Optional[str], tz: str = "Asia/Tokyo") -> float:
    """Days elapsed since the given ISO timestamp (0 if None or future)."""
    if not ts:
        return 0.0
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz))
        delta = datetime.now(ZoneInfo(tz)) - dt
        return max(0.0, delta.total_seconds() / 86400.0)
    except Exception:
        return 0.0


def ensure_memory_strength_row(
    conn: sqlite3.Connection, key: str, importance: float, emotion_intensity: float, created_at: str
) -> None:
    """Insert a memory_strength row if one doesn't exist (migration helper)."""
    s = initial_stability(emotion_intensity)
    conn.execute(
        """
        INSERT OR IGNORE INTO memory_strength (key, strength, stability, last_decay_at)
        VALUES (?, ?, ?, ?)
        """,
        (key, importance, s, created_at),
    )


# ── Recall boost ─────────────────────────────────────────────────────────────

def boost_on_recall(key: str, persona_db_path: str) -> None:
    """
    Called when a memory is accessed (read/search hit).

    Multiplies stability by STABILITY_GROWTH_FACTOR (capped at STABILITY_MAX),
    then resets strength to full (importance * 1.0) since the memory
    was just recalled — effectively restarting the decay clock.
    """
    now = _now_iso()
    try:
        with sqlite3.connect(persona_db_path) as conn:
            row = conn.execute(
                "SELECT stability FROM memory_strength WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return

            new_stability = min(row[0] * STABILITY_GROWTH_FACTOR, STABILITY_MAX)

            # Also fetch importance so we can set strength = importance (full recall)
            imp_row = conn.execute(
                "SELECT importance FROM memories WHERE key = ?", (key,)
            ).fetchone()
            new_strength = imp_row[0] if imp_row else 0.5

            conn.execute(
                """
                UPDATE memory_strength
                SET stability = ?, strength = ?, last_decay_at = ?
                WHERE key = ?
                """,
                (new_stability, new_strength, now, key),
            )
            # Update last_accessed on the memory itself
            conn.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE key = ?",
                (now, key),
            )
            conn.commit()
    except Exception as e:
        log_progress(f"⚠️  boost_on_recall failed ({key}): {e}")


# ── Decay pass ───────────────────────────────────────────────────────────────

def run_decay_pass(db_path: str, persona: str) -> int:
    """
    Apply Ebbinghaus decay to all memories for one persona.

    Updates `strength` in memory_strength table.
    Does NOT touch `importance`.

    Returns:
        Number of memories updated
    """
    cfg = load_config()
    tz = cfg.get("timezone", "Asia/Tokyo")
    now = _now_iso(tz)
    updated = 0

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT m.key, m.importance, m.emotion_intensity, m.last_accessed, m.created_at,
                       ms.stability
                FROM memories m
                LEFT JOIN memory_strength ms ON m.key = ms.key
                """,
            ).fetchall()

            for key, importance, emotion_intensity, last_accessed, created_at, stability in rows:
                # Determine reference timestamp for decay
                ref_ts = last_accessed or created_at
                days = _days_since(ref_ts, tz)

                s = stability if stability is not None else initial_stability(emotion_intensity or 0.0)
                retention = ebbinghaus_retention(days, s)
                new_strength = compute_strength(importance or 0.5, retention)

                conn.execute(
                    """
                    INSERT INTO memory_strength (key, strength, stability, last_decay_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        strength = excluded.strength,
                        last_decay_at = excluded.last_decay_at
                    """,
                    (key, new_strength, s, now),
                )
                updated += 1

            conn.commit()

        log_progress(f"📉 Ebbinghaus decay: updated {updated} memories (persona={persona})")
    except Exception as e:
        log_progress(f"❌ decay pass failed (persona={persona}): {e}")

    return updated


# ── Background worker ─────────────────────────────────────────────────────────

def _get_all_personas() -> List[Tuple[str, str]]:
    """Return list of (persona_name, db_path) for all existing persona dirs."""
    from src.utils.config_utils import ensure_memory_root
    import os
    memory_root = ensure_memory_root()
    result = []
    if not os.path.isdir(memory_root):
        return result
    for name in os.listdir(memory_root):
        db_path = os.path.join(memory_root, name, "memory.db")
        if os.path.isfile(db_path):
            result.append((name, db_path))
    return result


def _decay_worker_loop() -> None:
    interval_secs = DECAY_WORKER_INTERVAL_HOURS * 3600
    log_progress(f"🧠 Ebbinghaus decay worker started (interval={DECAY_WORKER_INTERVAL_HOURS}h)")

    while not _decay_stop_event.is_set():
        try:
            for persona, db_path in _get_all_personas():
                run_decay_pass(db_path, persona)
        except Exception as e:
            log_progress(f"❌ Ebbinghaus worker error: {e}")

        _decay_stop_event.wait(interval_secs)

    log_progress("🛑 Ebbinghaus decay worker stopped")


def start_ebbinghaus_worker() -> None:
    """Start the background decay worker thread (idempotent)."""
    global _decay_thread

    if _decay_thread is not None and _decay_thread.is_alive():
        return

    _decay_stop_event.clear()
    _decay_thread = threading.Thread(
        target=_decay_worker_loop,
        name="ebbinghaus-decay",
        daemon=True,
    )
    _decay_thread.start()
    log_progress("✅ Ebbinghaus decay worker thread started")


def stop_ebbinghaus_worker() -> None:
    """Signal the decay worker to stop."""
    _decay_stop_event.set()


# ── Legacy compatibility stubs ────────────────────────────────────────────────
# These preserve the old API surface so existing callers don't break.

def calculate_time_decay(created_at: str, last_accessed: Optional[str] = None) -> float:
    """Legacy: returns Ebbinghaus retention with stability=1.0."""
    days = _days_since(last_accessed or created_at)
    return ebbinghaus_retention(days, 1.0)


def apply_importance_decay(
    importance: float,
    created_at: str,
    emotion_intensity: float = 0.0,
    last_accessed: Optional[str] = None,
) -> float:
    """Legacy: compute_strength with initial stability."""
    days = _days_since(last_accessed or created_at)
    s = initial_stability(emotion_intensity)
    return compute_strength(importance, ebbinghaus_retention(days, s))


def decay_all_memories(dry_run: bool = True) -> Dict[str, float]:
    """Legacy: run decay pass for current persona's DB."""
    from src.utils.persona_utils import get_current_persona
    persona = get_current_persona()
    db_path = get_db_path(persona)

    cfg = load_config()
    tz = cfg.get("timezone", "Asia/Tokyo")
    results: Dict[str, float] = {}

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT m.key, m.importance, m.emotion_intensity, m.last_accessed, m.created_at,
                       ms.stability
                FROM memories m LEFT JOIN memory_strength ms ON m.key = ms.key
                """
            ).fetchall()

            for key, importance, emotion_intensity, last_accessed, created_at, stability in rows:
                ref_ts = last_accessed or created_at
                days = _days_since(ref_ts, tz)
                s = stability if stability is not None else initial_stability(emotion_intensity or 0.0)
                new_strength = compute_strength(importance or 0.5, ebbinghaus_retention(days, s))
                results[key] = new_strength

                if not dry_run:
                    conn.execute(
                        "UPDATE memory_strength SET strength = ? WHERE key = ?",
                        (new_strength, key),
                    )

            if not dry_run:
                conn.commit()
    except Exception as e:
        log_progress(f"❌ decay_all_memories failed: {e}")

    return results
