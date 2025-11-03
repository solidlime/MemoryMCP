"""
Self-Summarization (Metamemory) Module for Memory MCP.

Phase 28.4: Implements periodic memory summarization to create metamemory nodes.
Compresses multiple related memories into abstract summary nodes.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from zoneinfo import ZoneInfo
from config_utils import load_config
from persona_utils import get_db_path, get_current_persona
from core.memory_db import save_memory_to_db, generate_auto_key


def extract_memories_by_period(
    start_date: str,
    end_date: str,
    min_importance: float = 0.3
) -> List[Dict]:
    """
    Extract memories from a specific time period.
    
    Args:
        start_date: Start date (ISO 8601 format)
        end_date: End date (ISO 8601 format)
        min_importance: Minimum importance threshold (default: 0.3)
    
    Returns:
        List of memory dicts sorted by importance × emotion_intensity
    """
    db_path = get_db_path()
    memories = []
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT key, content, created_at, importance, emotion, emotion_intensity, tags
                FROM memories
                WHERE created_at >= ? AND created_at <= ? AND importance >= ?
                ORDER BY (importance * COALESCE(emotion_intensity, 0.5)) DESC
            ''', (start_date, end_date, min_importance))
            
            rows = cursor.fetchall()
            
            for row in rows:
                key, content, created_at, importance, emotion, emotion_intensity, tags_json = row
                memories.append({
                    "key": key,
                    "content": content,
                    "created_at": created_at,
                    "importance": importance if importance else 0.5,
                    "emotion": emotion if emotion else "neutral",
                    "emotion_intensity": emotion_intensity if emotion_intensity else 0.0,
                    "tags": json.loads(tags_json) if tags_json else [],
                    "score": (importance if importance else 0.5) * (emotion_intensity if emotion_intensity else 0.5)
                })
        
        return memories
    
    except Exception as e:
        print(f"⚠️  Failed to extract memories by period: {e}")
        return []


def calculate_dominant_emotion(memories: List[Dict]) -> Tuple[str, float]:
    """
    Calculate the dominant emotion from a list of memories.
    
    Args:
        memories: List of memory dicts with 'emotion' and 'emotion_intensity'
    
    Returns:
        Tuple of (dominant_emotion, average_intensity)
    """
    if not memories:
        return ("neutral", 0.0)
    
    emotion_scores = {}
    
    for mem in memories:
        emotion = mem.get("emotion", "neutral")
        intensity = mem.get("emotion_intensity", 0.0)
        
        if emotion not in emotion_scores:
            emotion_scores[emotion] = []
        emotion_scores[emotion].append(intensity)
    
    # Calculate average intensity per emotion
    emotion_averages = {
        emotion: sum(intensities) / len(intensities)
        for emotion, intensities in emotion_scores.items()
    }
    
    # Find dominant emotion (highest average intensity)
    if emotion_averages:
        dominant_emotion = max(emotion_averages.items(), key=lambda x: x[1])
        return dominant_emotion
    
    return ("neutral", 0.0)


def generate_summary_content(
    memories: List[Dict],
    period_description: str = "この期間"
) -> str:
    """
    Generate summary content from memories using LLM.
    
    Args:
        memories: List of memory dicts to summarize
        period_description: Human-readable period description (e.g., "2025年11月第1週")
    
    Returns:
        Summary text
    
    Note:
        This is a simplified version. In production, this would call an LLM API.
        For now, it creates a structured summary from memory metadata.
    """
    if not memories:
        return f"{period_description}の記憶なし"
    
    # Extract key themes from tags
    all_tags = []
    for mem in memories:
        all_tags.extend(mem.get("tags", []))
    
    tag_counts = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    themes = [tag for tag, _ in top_tags] if top_tags else []
    
    # Calculate statistics
    avg_importance = sum(m.get("importance", 0.5) for m in memories) / len(memories)
    dominant_emotion, avg_intensity = calculate_dominant_emotion(memories)
    
    # Get top memories by score
    top_memories = sorted(memories, key=lambda x: x.get("score", 0), reverse=True)[:5]
    highlights = [m.get("content", "")[:100] for m in top_memories]
    
    # Construct summary
    summary_parts = [
        f"{period_description}の記憶要約:",
        f"- 記憶数: {len(memories)}件",
        f"- 支配的感情: {dominant_emotion} (強度: {avg_intensity:.2f})",
        f"- 平均重要度: {avg_importance:.2f}",
    ]
    
    if themes:
        summary_parts.append(f"- 主なテーマ: {', '.join(themes)}")
    
    summary_parts.append("\n主な出来事:")
    for i, highlight in enumerate(highlights[:3], 1):
        summary_parts.append(f"{i}. {highlight}...")
    
    return "\n".join(summary_parts)


def create_summary_node(
    memories: List[Dict],
    period_start: str,
    period_end: str,
    period_description: str = "期間"
) -> Optional[str]:
    """
    Create a summary (metamemory) node for a period of memories.
    
    Args:
        memories: List of memory dicts to summarize
        period_start: Period start date (ISO 8601)
        period_end: Period end date (ISO 8601)
        period_description: Human-readable period description
    
    Returns:
        Summary node key if successful, None otherwise
    """
    if not memories:
        print(f"⚠️  No memories to summarize for {period_description}")
        return None
    
    try:
        # Generate summary content
        summary_content = generate_summary_content(memories, period_description)
        
        # Calculate summary metadata
        avg_importance = sum(m.get("importance", 0.5) for m in memories) / len(memories)
        dominant_emotion, avg_intensity = calculate_dominant_emotion(memories)
        
        # Extract all related keys
        related_keys = [m["key"] for m in memories]
        
        # Collect all tags
        all_tags = set()
        for m in memories:
            all_tags.update(m.get("tags", []))
        
        # Generate summary key
        summary_key = f"summary_{period_start[:10].replace('-', '')}"
        
        # Save summary node to database
        save_memory_to_db(
            key=summary_key,
            content=summary_content,
            tags=list(all_tags),
            importance=min(1.0, avg_importance * 1.2),  # Boost summary importance
            emotion=dominant_emotion,
            emotion_intensity=avg_intensity,
            related_keys=related_keys,
            summary_ref=None  # Summary nodes don't reference other summaries
        )
        
        print(f"✅ Created summary node: {summary_key}")
        print(f"   - Summarized {len(memories)} memories")
        print(f"   - Emotion: {dominant_emotion} ({avg_intensity:.2f})")
        print(f"   - Importance: {avg_importance:.2f}")
        
        return summary_key
    
    except Exception as e:
        print(f"⚠️  Failed to create summary node: {e}")
        import traceback
        traceback.print_exc()
        return None


def link_memories_to_summary(memory_keys: List[str], summary_key: str) -> int:
    """
    Link memories to their summary node.
    
    Args:
        memory_keys: List of memory keys to link
        summary_key: Summary node key
    
    Returns:
        Number of memories successfully linked
    """
    db_path = get_db_path()
    linked_count = 0
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            for key in memory_keys:
                cursor.execute('''
                    UPDATE memories
                    SET summary_ref = ?
                    WHERE key = ?
                ''', (summary_key, key))
                linked_count += 1
            
            conn.commit()
            print(f"✅ Linked {linked_count} memories to summary: {summary_key}")
        
        return linked_count
    
    except Exception as e:
        print(f"⚠️  Failed to link memories to summary: {e}")
        return 0


def summarize_period(
    period_start: str,
    period_end: str,
    period_description: str = "期間",
    min_importance: float = 0.3,
    link_memories: bool = True
) -> Optional[str]:
    """
    Complete workflow: Extract, summarize, and link memories for a period.
    
    Args:
        period_start: Start date (ISO 8601)
        period_end: End date (ISO 8601)
        period_description: Human-readable description
        min_importance: Minimum importance threshold
        link_memories: Whether to link memories to summary
    
    Returns:
        Summary key if successful, None otherwise
    """
    print(f"📝 Summarizing period: {period_description}")
    print(f"   Range: {period_start} to {period_end}")
    
    # Extract memories
    memories = extract_memories_by_period(period_start, period_end, min_importance)
    
    if not memories:
        print(f"⚠️  No memories found for period")
        return None
    
    # Create summary node
    summary_key = create_summary_node(memories, period_start, period_end, period_description)
    
    if not summary_key:
        return None
    
    # Link memories to summary
    if link_memories:
        memory_keys = [m["key"] for m in memories]
        link_memories_to_summary(memory_keys, summary_key)
    
    return summary_key


def summarize_last_week() -> Optional[str]:
    """
    Summarize memories from the last 7 days.
    
    Returns:
        Summary key if successful, None otherwise
    """
    cfg = load_config()
    timezone = cfg.get("timezone", "Asia/Tokyo")
    now = datetime.now(ZoneInfo(timezone))
    
    end_date = now.isoformat()
    start_date = (now - timedelta(days=7)).isoformat()
    
    period_desc = f"{now.year}年{now.month}月第{(now.day-1)//7+1}週"
    
    return summarize_period(start_date, end_date, period_desc)


def summarize_last_day() -> Optional[str]:
    """
    Summarize memories from the last 24 hours.
    
    Returns:
        Summary key if successful, None otherwise
    """
    cfg = load_config()
    timezone = cfg.get("timezone", "Asia/Tokyo")
    now = datetime.now(ZoneInfo(timezone))
    
    end_date = now.isoformat()
    start_date = (now - timedelta(days=1)).isoformat()
    
    period_desc = f"{now.year}年{now.month}月{now.day}日"
    
    return summarize_period(start_date, end_date, period_desc)
