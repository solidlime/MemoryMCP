"""
MCP Resources for Memory MCP
Provides read-only resources for memory info, metrics, stats, and cleanup suggestions
"""

import os
import json
import sqlite3
import re
from collections import Counter
from datetime import datetime, timedelta

# Core imports
from core import load_persona_context, calculate_time_diff

# Utility imports
from src.utils.persona_utils import get_db_path, get_current_persona, get_persona_dir
from src.utils.vector_utils import get_vector_count, get_vector_metrics, reranker as _reranker
from src.utils.db_utils import (
    db_count_entries as db_count_entries_impl,
    db_sum_content_chars as db_sum_content_chars_impl,
)


def _get_rebuild_config():
    """Get vector rebuild configuration."""
    from src.utils.vector_utils import REBUILD_MODE, IDLE_SECONDS, MIN_REBUILD_INTERVAL
    return {
        "mode": REBUILD_MODE,
        "idle_seconds": IDLE_SECONDS,
        "min_interval": MIN_REBUILD_INTERVAL,
    }


def db_count_entries() -> int:
    """Count total entries in database."""
    return db_count_entries_impl(get_db_path())


def db_sum_content_chars() -> int:
    """Sum total content characters in database."""
    return db_sum_content_chars_impl(get_db_path())


# ========================================
# Resource: Memory Info
# ========================================

def get_memory_info() -> str:
    """Provide memory service info (DB-source of truth)"""
    entries = db_count_entries()
    total_chars = db_sum_content_chars()
    vector_count = get_vector_count()
    db_path = get_db_path()
    persona = get_current_persona()
    cfg = _get_rebuild_config()
    return (
        f"User Memory System Info:\n"
        f"- Entries: {entries}\n"
        f"- Total chars: {total_chars}\n"
        f"- Vector Store: {vector_count} documents\n"
        f"- Reranker: {'Available' if _reranker else 'Not available'}\n"
        f"- Database: {db_path}\n"
        f"- Persona: {persona}\n"
        f"- Vector Rebuild: mode={cfg.get('mode')}, idle_seconds={cfg.get('idle_seconds')}, min_interval={cfg.get('min_interval')}\n"
        f"- Tools: create_memory, read_memory, update_memory, delete_memory, list_memory, search_memory, search_memory_by_date, clean_memory\n"
        f"- Key format: memory_YYYYMMDDHHMMSS\n"
        f"- Save format: 'User is ...'\n"
    )


# ========================================
# Resource: Memory Metrics
# ========================================

def get_memory_metrics() -> str:
    """
    Provide detailed metrics for monitoring and debugging.
    
    Returns:
        Formatted string with:
        - Embeddings model name and load status
        - Reranker model name and load status
        - Vector store document count
        - Dirty status (rebuild pending)
        - Last write/rebuild timestamps
        - Rebuild configuration
    """
    metrics = get_vector_metrics()
    persona = get_current_persona()
    
    # Format timestamps
    def format_ts(ts: float) -> str:
        if ts > 0:
            return datetime.fromtimestamp(ts).isoformat()
        return "Never"
    
    last_write = format_ts(metrics["last_write_ts"])
    last_rebuild = format_ts(metrics["last_rebuild_ts"])
    
    rebuild_cfg = metrics["rebuild_config"]
    
    return (
        f"📊 Memory Metrics (persona: {persona}):\n"
        f"\n"
        f"🧠 Models:\n"
        f"  - Embeddings: {metrics['embeddings_model'] or 'Not loaded'} "
        f"({'✅ Loaded' if metrics['embeddings_loaded'] else '❌ Not loaded'})\n"
        f"  - Reranker: {metrics['reranker_model'] or 'Not loaded'} "
        f"({'✅ Loaded' if metrics['reranker_loaded'] else '❌ Not loaded'})\n"
        f"\n"
        f"📦 Vector Store:\n"
        f"  - Documents: {metrics['vector_count']}\n"
        f"  - Dirty: {'✅ Yes (rebuild pending)' if metrics['dirty'] else '❌ No'}\n"
        f"\n"
        f"⏰ Timestamps:\n"
        f"  - Last Write: {last_write}\n"
        f"  - Last Rebuild: {last_rebuild}\n"
        f"\n"
        f"⚙️  Rebuild Config:\n"
        f"  - Mode: {rebuild_cfg['mode']}\n"
        f"  - Idle Seconds: {rebuild_cfg['idle_seconds']}\n"
        f"  - Min Interval: {rebuild_cfg['min_interval']}\n"
    )


# ========================================
# Resource: Memory Statistics Dashboard
# ========================================

def get_memory_stats() -> str:
    """
    Provide comprehensive memory statistics dashboard.
    
    Returns:
        Formatted string with:
        - Total memory count and date range
        - Tag distribution (with percentages)
        - Emotion distribution (with percentages)
        - Timeline (daily memory counts for last 7 days)
        - Link analysis (most mentioned [[links]])
    """
    db_path = get_db_path()
    persona = get_current_persona()
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # ========== Basic Stats ==========
            cursor.execute("SELECT COUNT(*) FROM memories")
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                return f"📊 Memory Statistics (persona: {persona}):\n\n💡 No memories yet!"
            
            # Get date range
            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM memories")
            min_date_str, max_date_str = cursor.fetchone()
            min_date = datetime.fromisoformat(min_date_str).date()
            max_date = datetime.fromisoformat(max_date_str).date()
            date_range_days = (max_date - min_date).days + 1
            avg_per_day = total_count / date_range_days if date_range_days > 0 else 0
            
            # ========== Tag Distribution ==========
            cursor.execute("SELECT tags FROM memories WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = Counter()
            for row in cursor.fetchall():
                tags_json = row[0]
                try:
                    tags_list = json.loads(tags_json)
                    tag_counter.update(tags_list)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # ========== Emotion Distribution ==========
            # Load persona context to get emotion history
            context = load_persona_context()
            emotion_history = context.get("emotion_history", [])
            emotion_counter = Counter()
            for entry in emotion_history:
                emotion_type = entry.get("emotion_type")
                if emotion_type:
                    emotion_counter[emotion_type] += 1
            
            # ========== Timeline (last 7 days) ==========
            cursor.execute("SELECT created_at FROM memories")
            date_counter = Counter()
            for row in cursor.fetchall():
                created_at = datetime.fromisoformat(row[0]).date()
                date_counter[created_at] += 1
            
            # Get last 7 days
            today = datetime.now().date()
            timeline = []
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                count = date_counter.get(day, 0)
                timeline.append((day, count))
            
            # ========== Link Analysis ==========
            cursor.execute("SELECT content FROM memories")
            link_counter = Counter()
            link_pattern = re.compile(r'\[\[(.+?)\]\]')
            for row in cursor.fetchall():
                content = row[0]
                matches = link_pattern.findall(content)
                link_counter.update(matches)
            
            # ========== Format Output ==========
            output = f"📊 Memory Statistics Dashboard (persona: {persona})\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Basic stats
            output += f"📦 Total Memories: {total_count}\n"
            output += f"📅 Date Range: {min_date} ~ {max_date} ({date_range_days} days)\n"
            output += f"📈 Average per day: {avg_per_day:.2f} memories\n\n"
            
            # Tag distribution
            if tag_counter:
                output += "🏷️  Tag Distribution:\n"
                for tag, count in tag_counter.most_common(10):
                    percentage = (count / total_count) * 100
                    output += f"  - {tag}: {count} ({percentage:.1f}%)\n"
                output += "\n"
            
            # Emotion distribution
            if emotion_counter:
                output += "😊 Emotion Distribution:\n"
                total_emotions = sum(emotion_counter.values())
                for emotion, count in emotion_counter.most_common(10):
                    percentage = (count / total_emotions) * 100
                    output += f"  - {emotion}: {count} ({percentage:.1f}%)\n"
                output += "\n"
            
            # Timeline
            output += "📆 Timeline (last 7 days):\n"
            max_count = max([count for _, count in timeline]) if timeline else 1
            for day, count in timeline:
                bar_length = int((count / max_count) * 10) if max_count > 0 else 0
                bar = "█" * bar_length
                output += f"  {day}: {bar} {count}\n"
            output += "\n"
            
            # Link analysis
            if link_counter:
                output += "🔗 Link Analysis (top 10):\n"
                top_links = link_counter.most_common(10)
                output += "  Most mentioned: "
                link_strs = [f"[[{link}]]({count})" for link, count in top_links]
                output += ", ".join(link_strs)
                output += "\n"
            
            return output
            
    except Exception as e:
        return f"❌ Error generating statistics: {e}"


# ========================================
# Resource: Cleanup Suggestions (Phase 21)
# ========================================

def get_cleanup_suggestions() -> str:
    """
    Provide cleanup suggestions generated by idle worker.
    
    Returns:
        Formatted cleanup suggestions with merge commands
    """
    try:
        persona = get_current_persona()
        persona_dir = get_persona_dir(persona)
        suggestions_file = os.path.join(persona_dir, "cleanup_suggestions.json")
        
        if not os.path.exists(suggestions_file):
            return (
                f"🧹 Cleanup Suggestions (persona: {persona})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"No suggestions available yet.\n\n"
                f"💡 Suggestions are generated automatically after 30 minutes of idle time.\n"
                f"   You can also run: detect_duplicates(threshold=0.90)\n"
            )
        
        # Load suggestions
        with open(suggestions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Calculate time since generation
        generated_at = datetime.fromisoformat(data['generated_at'])
        now = datetime.now(generated_at.tzinfo)
        time_diff = now - generated_at
        
        if time_diff.days > 0:
            time_ago = f"{time_diff.days}日前"
        elif time_diff.seconds >= 3600:
            hours = time_diff.seconds // 3600
            time_ago = f"{hours}時間前"
        else:
            minutes = time_diff.seconds // 60
            time_ago = f"{minutes}分前"
        
        duplicates = data.get('duplicates', [])
        threshold = data.get('threshold', 0.90)
        
        if not duplicates:
            return (
                f"🧹 Cleanup Suggestions (persona: {persona})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✨ No duplicate memories found!\n"
                f"Generated: {time_ago} (threshold: {threshold:.2f})\n"
            )
        
        # Format output
        result = f"🧹 Cleanup Suggestions (persona: {persona})\n"
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"Generated: {time_ago} | Threshold: {threshold:.2f} (≥{threshold*100:.0f}% similarity)\n"
        result += f"Found {len(duplicates)} duplicate pairs\n\n"
        
        for idx, dup in enumerate(duplicates[:10], 1):  # Show top 10
            key1 = dup['key1']
            key2 = dup['key2']
            content1 = dup['content1']
            content2 = dup['content2']
            similarity = dup['similarity']
            
            result += f"━━━ Pair {idx} (similarity: {similarity:.3f} = {similarity*100:.1f}%) ━━━\n\n"
            result += f"Memory 1: [{key1}]\n"
            result += f"  {content1[:150]}{'...' if len(content1) > 150 else ''}\n\n"
            result += f"Memory 2: [{key2}]\n"
            result += f"  {content2[:150]}{'...' if len(content2) > 150 else ''}\n\n"
            result += f"💡 To merge: merge_memories(memory_keys=['{key1}', '{key2}'])\n\n"
        
        if len(duplicates) > 10:
            result += f"... and {len(duplicates) - 10} more pairs.\n"
        
        result += f"\n💡 Tip: Review suggestions and use merge_memories to consolidate duplicates.\n"
        result += f"💡 Persona: {persona}"
        
        return result
        
    except Exception as e:
        return f"❌ Error loading cleanup suggestions: {str(e)}"
