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


def _call_llm_api(memories: List[Dict], period_description: str, config: Dict) -> Optional[str]:
    """
    Call LLM API to generate natural language summary.
    
    Args:
        memories: List of memory dicts to summarize
        period_description: Human-readable period description
        config: Configuration dict with LLM settings
    
    Returns:
        LLM-generated summary text, or None on failure
    """
    try:
        import requests
        
        api_url = config.get("summarization", {}).get("llm_api_url")
        api_key = config.get("summarization", {}).get("llm_api_key")
        model = config.get("summarization", {}).get("llm_model", "anthropic/claude-3.5-sonnet")
        max_tokens = config.get("summarization", {}).get("llm_max_tokens", 500)
        custom_prompt = config.get("summarization", {}).get("llm_prompt")
        
        if not api_key:
            print("⚠️  LLM API key not configured")
            return None
        
        if not api_url:
            print("⚠️  LLM API URL not configured")
            return None
        
        # Prepare memory content for LLM
        memory_texts = []
        for mem in memories[:10]:  # Limit to top 10 to avoid token overflow
            content = mem.get("content", "")[:200]  # First 200 chars
            emotion = mem.get("emotion", "neutral")
            intensity = mem.get("emotion_intensity", 0.0)
            importance = mem.get("importance", 0.5)
            memory_texts.append(f"- [{emotion}/{intensity:.1f}/重要度{importance:.1f}] {content}")
        
        memories_str = "\n".join(memory_texts)
        
        # Use custom prompt if provided, otherwise use default
        if custom_prompt:
            # Replace placeholders in custom prompt
            prompt = custom_prompt.replace("{period}", period_description).replace("{memories}", memories_str)
        else:
            # Default prompt
            prompt = f"""以下は{period_description}の記憶です。この期間全体の印象を自然な日本語で要約してください。

記憶一覧:
{memories_str}

要件:
- 200文字程度で簡潔に
- 全体的な感情のトーンを含める
- 主要な出来事やテーマを含める
- 箇条書きではなく、自然な文章で"""
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Add HTTP-Referer for OpenRouter
        if "openrouter.ai" in api_url:
            headers["HTTP-Referer"] = "https://github.com/solidlime/MemoryMCP"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️  LLM API error: {response.status_code} - {response.text}")
            return None
        
        result = response.json()
        summary = result["choices"][0]["message"]["content"].strip()
        
        print(f"✅ LLM summary generated ({len(summary)} chars)")
        return summary
    
    except Exception as e:
        print(f"⚠️  Failed to call LLM API: {e}")
        import traceback
        traceback.print_exc()
        return None


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
    Generate summary content from memories.
    Uses LLM if configured, otherwise falls back to structured template.
    
    Args:
        memories: List of memory dicts to summarize
        period_description: Human-readable period description (e.g., "2025年11月第1週")
    
    Returns:
        Summary text
    """
    if not memories:
        return f"{period_description}の記憶なし"
    
    config = load_config()
    use_llm = config.get("summarization", {}).get("use_llm", False)
    
    # Try LLM summary if enabled
    if use_llm:
        print("🤖 Attempting LLM-based summary generation...")
        llm_summary = _call_llm_api(memories, period_description, config)
        if llm_summary:
            return llm_summary
        else:
            print("⚠️  LLM summary failed, falling back to structured template")
    
    # Fallback: Structured template summary
    print("📊 Using structured template summary")
    
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
    period_description: str,
    persona_name: str = "default"
) -> Optional[str]:
    """
    Create a summary metamemory node from a list of memories.
    
    Args:
        memories: List of memory dicts to summarize
        period_description: Human-readable period description
        persona_name: Persona name
    
    Returns:
        Summary memory key, or None if summary generation failed
    """
    if not memories:
        print(f"⚠️  No memories to summarize for {period_description}")
        return None
    
    # Generate summary content
    summary_content = generate_summary_content(memories, period_description)
    
    # Check if summary generation failed
    if not summary_content or summary_content.startswith(f"{period_description}の記憶なし"):
        print(f"❌ Summary generation failed for {period_description}")
        return None
    
    # Calculate aggregated metadata
    avg_importance = sum(m.get("importance", 0.5) for m in memories) / len(memories)
    dominant_emotion, emotion_intensity = calculate_dominant_emotion(memories)
    
    # Collect all unique tags
    all_tags = set()
    for mem in memories:
        all_tags.update(mem.get("tags", []))
    all_tags.add("summary")  # Mark as summary node
    
    # Create summary node
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    summary_key = f"summary_{now}"
    
    success = save_memory_to_db(
        key=summary_key,
        content=summary_content,
        tags=list(all_tags),
        importance=avg_importance,
        emotion=dominant_emotion,
        emotion_intensity=emotion_intensity,
        physical_state=None,
        mental_state=None,
        environment=None,
        relationship_status=None,
        action_tag=None,
        related_keys=None,  # Will be set by link_memories_to_summary
        summary_ref=None  # Summary nodes don't reference other summaries
    )
    
    if not success:
        print(f"❌ Failed to save summary node: {summary_key}")
        return None
    
    print(f"✅ Created summary node: {summary_key}")
    return summary_key


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
    summary_key = create_summary_node(memories, period_description)
    
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
