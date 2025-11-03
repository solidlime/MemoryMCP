"""
Forgetting Module for Memory MCP.

Phase 28.3: Implements time-based memory decay and forgetting algorithms.
Memories fade over time unless they are recalled or have strong emotional intensity.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo
from src.utils.config_utils import load_config
from src.utils.persona_utils import get_db_path


def calculate_time_decay(created_at: str, last_accessed: Optional[str] = None) -> float:
    """
    Calculate time decay factor for a memory.
    
    Args:
        created_at: ISO 8601 timestamp of memory creation
        last_accessed: ISO 8601 timestamp of last access (optional, defaults to created_at)
    
    Returns:
        float: Decay factor (0.0 to 1.0, where 1.0 = no decay)
    
    Formula:
        decay = 1.0 / (1.0 + days_since_access / 30)
        
    Examples:
        - 0 days: 1.0 (no decay)
        - 30 days: 0.5 (half strength)
        - 90 days: 0.25 (quarter strength)
        - 365 days: ~0.076 (very weak)
    """
    cfg = load_config()
    timezone = cfg.get("timezone", "Asia/Tokyo")
    now = datetime.now(ZoneInfo(timezone))
    
    # Use last_accessed if available, otherwise use created_at
    reference_time = last_accessed if last_accessed else created_at
    
    try:
        reference_dt = datetime.fromisoformat(reference_time)
        if reference_dt.tzinfo is None:
            reference_dt = reference_dt.replace(tzinfo=ZoneInfo(timezone))
        
        delta = now - reference_dt
        days_since = delta.total_seconds() / 86400  # Convert to days
        
        # Decay formula: 1.0 / (1.0 + days / 30)
        decay = 1.0 / (1.0 + days_since / 30.0)
        
        return max(0.0, min(1.0, decay))
    
    except Exception as e:
        print(f"⚠️  Failed to calculate time decay: {e}")
        return 1.0  # Default to no decay on error


def apply_importance_decay(
    importance: float,
    created_at: str,
    emotion_intensity: float = 0.0,
    last_accessed: Optional[str] = None
) -> float:
    """
    Apply time-based decay to importance score.
    
    Args:
        importance: Current importance score (0.0-1.0)
        created_at: ISO 8601 timestamp of memory creation
        emotion_intensity: Emotion intensity (0.0-1.0, higher = slower decay)
        last_accessed: ISO 8601 timestamp of last access
    
    Returns:
        float: Decayed importance score (0.0-1.0)
    
    Algorithm:
        - Strong emotions (emotion_intensity > 0.7) decay 70% slower
        - Medium emotions (0.5-0.7) decay 50% slower
        - Weak emotions (<0.5) decay at normal rate
    """
    time_decay = calculate_time_decay(created_at, last_accessed)
    
    # Emotion-based decay resistance
    if emotion_intensity > 0.7:
        # Strong emotions: 70% resistance to decay
        decay_factor = 0.3 + (time_decay * 0.7)
    elif emotion_intensity > 0.5:
        # Medium emotions: 50% resistance to decay
        decay_factor = 0.5 + (time_decay * 0.5)
    else:
        # Weak/neutral emotions: normal decay
        decay_factor = time_decay
    
    # Apply decay to importance
    decayed_importance = importance * decay_factor
    
    return max(0.0, min(1.0, decayed_importance))


def mark_memories_for_deletion(min_importance: float = 0.0, has_summary: bool = True) -> List[str]:
    """
    Find memories that should be deleted based on decay and summarization status.
    
    Args:
        min_importance: Minimum importance threshold (memories below this are marked)
        has_summary: Only mark memories that have been summarized (summary_ref exists)
    
    Returns:
        List of memory keys to be deleted
    
    Deletion criteria:
        1. importance < min_importance (default: 0.0)
        2. summary_ref is not NULL (memory has been summarized)
    """
    db_path = get_db_path()
    to_delete = []
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            if has_summary:
                # Only mark memories with summary_ref
                cursor.execute('''
                    SELECT key, content, importance, emotion_intensity, summary_ref
                    FROM memories
                    WHERE importance < ? AND summary_ref IS NOT NULL
                ''', (min_importance,))
            else:
                # Mark all low-importance memories
                cursor.execute('''
                    SELECT key, content, importance, emotion_intensity, summary_ref
                    FROM memories
                    WHERE importance < ?
                ''', (min_importance,))
            
            rows = cursor.fetchall()
            
            for row in rows:
                key, content, importance, emotion_intensity, summary_ref = row
                to_delete.append(key)
                print(f"🗑️  Marked for deletion: {key} (importance: {importance:.3f}, emotion: {emotion_intensity:.3f}, summary: {summary_ref})")
        
        return to_delete
    
    except Exception as e:
        print(f"⚠️  Failed to mark memories for deletion: {e}")
        return []


def decay_all_memories(dry_run: bool = True) -> Dict[str, float]:
    """
    Apply time decay to all memories in the database.
    
    Args:
        dry_run: If True, only simulate decay without updating database
    
    Returns:
        Dict mapping memory keys to new importance scores
    
    Note:
        This function should be called periodically (e.g., daily) to simulate forgetting.
    """
    db_path = get_db_path()
    decayed_importances = {}
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Fetch all memories with their metadata
            cursor.execute('''
                SELECT key, content, created_at, importance, emotion_intensity
                FROM memories
            ''')
            rows = cursor.fetchall()
            
            for row in rows:
                key, content, created_at, current_importance, emotion_intensity = row
                
                # Calculate decayed importance
                new_importance = apply_importance_decay(
                    current_importance,
                    created_at,
                    emotion_intensity if emotion_intensity else 0.0
                )
                
                decayed_importances[key] = new_importance
                
                # Update database if not dry run
                if not dry_run and new_importance != current_importance:
                    cursor.execute('''
                        UPDATE memories
                        SET importance = ?
                        WHERE key = ?
                    ''', (new_importance, key))
                    
                    print(f"📉 Decayed: {key} | {current_importance:.3f} → {new_importance:.3f}")
            
            if not dry_run:
                conn.commit()
                print(f"✅ Applied decay to {len(decayed_importances)} memories")
            else:
                print(f"🔍 Dry run: Would decay {len(decayed_importances)} memories")
        
        return decayed_importances
    
    except Exception as e:
        print(f"⚠️  Failed to decay memories: {e}")
        return {}
