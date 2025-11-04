"""
Analysis tools for memory-mcp.

This module provides advanced memory analysis operations including
duplicate detection, merging, cleaning, similarity search, and sentiment analysis.
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional, List

from src.utils.persona_utils import get_current_persona, get_db_path
from core import (
    get_current_time,
    calculate_time_diff,
    save_memory_to_db,
    log_operation,
)
from src.utils.vector_utils import (
    update_memory_in_vector_store,
    find_similar_memories,
    detect_duplicate_memories,
    mark_vector_store_dirty,
    analyze_sentiment_text,
)


def _log_progress(message: str) -> None:
    """Internal logging function."""
    print(message, flush=True)


async def clean_memory(key: str) -> str:
    """
    Clean up memory content by removing duplicates and normalizing format.
    Args:
        key: Memory key to clean
    """
    try:
        db_path = get_db_path()
        
        # Get memory from database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content, created_at, tags FROM memories WHERE key = ?', (key,))
            row = cursor.fetchone()
        
        if not row:
            # Get available keys
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key FROM memories ORDER BY created_at DESC LIMIT 5')
                available_keys = [r[0] for r in cursor.fetchall()]
            
            if available_keys:
                return f"Key '{key}' not found. Recent keys: {', '.join(available_keys)}"
            else:
                return f"Key '{key}' not found. No memory data."
        
        original_content, created_at, tags_json = row
        existing_tags = json.loads(tags_json) if tags_json else []
        
        # Clean up content: remove duplicates, normalize whitespace
        lines = original_content.split('\n')
        seen_lines = set()
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and line not in seen_lines:
                seen_lines.add(line)
                cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # If no changes, return message
        if cleaned_content == original_content:
            return f"Memory '{key}' is already clean."
        
        now = datetime.now().isoformat()
        
        # Save to database (preserve tags and created_at)
        save_memory_to_db(key, cleaned_content, created_at, now, existing_tags)
        
        # Update vector store
        update_memory_in_vector_store(key, cleaned_content)
        
        log_operation("clean", key=key, 
                     before={"content": original_content, "created_at": created_at, "tags": existing_tags},
                     after={"content": cleaned_content, "created_at": created_at, "updated_at": now, "tags": existing_tags},
                     metadata={
                         "old_content_length": len(original_content),
                         "new_content_length": len(cleaned_content),
                         "lines_removed": len(lines) - len(cleaned_lines)
                     })
        
        return f"Cleaned: '{key}' (removed {len(lines) - len(cleaned_lines)} duplicate lines)"
    except Exception as e:
        log_operation("clean", key=key, success=False, error=str(e))
        return f"Failed to clean memory: {str(e)}"


async def find_related_memories(
    memory_key: str,
    top_k: int = 5
) -> str:
    """
    Find semantically similar memories using embeddings.
    
    **When to use this tool:**
    - Exploring connections between memories
    - Finding context for a specific memory
    - Discovering related topics or themes
    - Building knowledge graphs or clusters
    
    **When NOT to use:**
    - General search → use read_memory()
    - Don't have a specific memory key
    - Just browsing all memories → use search_memory()
    
    Args:
        memory_key: Memory key (format: memory_YYYYMMDDHHMMSS)
        top_k: Results to return (default: 5, max: 20)
        
    Returns:
        Related memories with similarity scores
    """
    try:
        persona = get_current_persona()
        
        # Validate input
        if not memory_key.startswith("memory_"):
            return "❌ Invalid memory key format. Expected: memory_YYYYMMDDHHMMSS"
        
        # Limit top_k to reasonable range
        top_k = min(max(1, top_k), 20)
        
        # Check if memory exists
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content, created_at FROM memories WHERE key = ?", (memory_key,))
            row = cursor.fetchone()
            
        if not row:
            return f"❌ Memory not found: {memory_key}"
        
        query_content, created_at = row
        
        # Find similar memories
        similar = find_similar_memories(memory_key, top_k)
        
        if not similar:
            return f"💡 No related memories found for {memory_key}"
        
        # Format output
        result = f"🔗 Related Memories for {memory_key}:\n"
        result += f"📝 Query: {query_content[:100]}{'...' if len(query_content) > 100 else ''}\n"
        result += f"📅 Created: {created_at}\n"
        result += f"\n{'='*50}\n"
        result += f"Found {len(similar)} related memories:\n\n"
        
        for idx, (key, content, score) in enumerate(similar, 1):
            # Get timestamp for related memory
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT created_at FROM memories WHERE key = ?", (key,))
                ts_row = cursor.fetchone()
                timestamp = ts_row[0] if ts_row else "Unknown"
            
            # Calculate time difference
            time_diff = calculate_time_diff(timestamp)
            
            result += f"{idx}. [{key}] (similarity: {score:.3f})\n"
            result += f"   📅 {time_diff['formatted_string']}前\n"
            result += f"   📝 {content[:150]}{'...' if len(content) > 150 else ''}\n\n"
        
        result += f"\n💡 Persona: {persona}"
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to find related memories: {e}")
        return f"❌ Error finding related memories: {str(e)}"


async def detect_duplicates(
    threshold: float = 0.85,
    max_pairs: int = 50
) -> str:
    """
    Detect duplicate or highly similar memory pairs.
    
    This tool helps identify memories that are very similar to each other,
    which might be:
    - Exact duplicates created by mistake
    - Multiple versions of the same information
    - Related memories that could be merged
    
    Args:
        threshold: Similarity threshold (0.0-1.0). Default 0.85 means 85% similar or more.
                  Higher values = stricter duplicate detection (only very similar pairs)
                  Lower values = looser detection (more pairs, including somewhat similar ones)
        max_pairs: Maximum number of duplicate pairs to return (default: 50)
        
    Returns:
        Formatted string with duplicate pairs sorted by similarity
    """
    try:
        persona = get_current_persona()
        
        # Validate threshold
        threshold = max(0.0, min(1.0, threshold))
        max_pairs = max(1, min(100, max_pairs))
        
        # Detect duplicates
        duplicates = detect_duplicate_memories(threshold, max_pairs)
        
        if not duplicates:
            return f"💡 No duplicate memories found (threshold: {threshold:.2f})\n\nTry lowering the threshold to find more similar pairs."
        
        # Format output
        result = f"🔍 Duplicate Memory Detection (persona: {persona})\n"
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"Threshold: {threshold:.2f} (similarity ≥ {threshold*100:.0f}%)\n"
        result += f"Found {len(duplicates)} duplicate pairs:\n\n"
        
        for idx, (key1, key2, content1, content2, similarity) in enumerate(duplicates, 1):
            # Get timestamps
            db_path = get_db_path()
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT created_at FROM memories WHERE key = ?", (key1,))
                ts1 = cursor.fetchone()[0]
                cursor.execute("SELECT created_at FROM memories WHERE key = ?", (key2,))
                ts2 = cursor.fetchone()[0]
            
            time_diff1 = calculate_time_diff(ts1)
            time_diff2 = calculate_time_diff(ts2)
            
            result += f"━━━ Pair {idx} (similarity: {similarity:.3f} = {similarity*100:.1f}%) ━━━\n\n"
            result += f"📝 Memory 1: [{key1}] ({time_diff1['formatted_string']}前)\n"
            result += f"   {content1[:200]}{'...' if len(content1) > 200 else ''}\n\n"
            result += f"📝 Memory 2: [{key2}] ({time_diff2['formatted_string']}前)\n"
            result += f"   {content2[:200]}{'...' if len(content2) > 200 else ''}\n\n"
        
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"💡 Tip: Use merge_memories tool to combine duplicate pairs.\n"
        result += f"💡 Persona: {persona}"
        
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to detect duplicates: {e}")
        return f"❌ Error detecting duplicates: {str(e)}"


async def merge_memories(
    memory_keys: List[str],
    merged_content: Optional[str] = None,
    keep_all_tags: bool = True,
    delete_originals: bool = True
) -> str:
    """
    Merge multiple memories into a single consolidated memory.
    
    This tool combines multiple related or duplicate memories into one,
    preserving important information while reducing clutter.
    
    Args:
        memory_keys: List of memory keys to merge (minimum 2, format: memory_YYYYMMDDHHMMSS)
        merged_content: Content for the merged memory. If None, contents are concatenated with newlines.
        keep_all_tags: If True, combine tags from all memories. If False, use tags from first memory only.
        delete_originals: If True, delete original memories after merge. If False, keep them.
        
    Returns:
        Success message with the new merged memory key, or error message
    """
    try:
        persona = get_current_persona()
        
        # Validate input
        if not memory_keys or len(memory_keys) < 2:
            return "❌ Please provide at least 2 memory keys to merge"
        
        if len(memory_keys) > 10:
            return "❌ Cannot merge more than 10 memories at once"
        
        for key in memory_keys:
            if not key.startswith("memory_"):
                return f"❌ Invalid memory key format: {key}"
        
        # Fetch all memories
        db_path = get_db_path()
        memories = []
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for key in memory_keys:
                cursor.execute(
                    "SELECT content, created_at, tags FROM memories WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if not row:
                    return f"❌ Memory not found: {key}"
                memories.append({
                    "key": key,
                    "content": row[0],
                    "created_at": row[1],
                    "tags": json.loads(row[2]) if row[2] else []
                })
        
        # Sort by timestamp (oldest first)
        memories.sort(key=lambda x: x["created_at"])
        oldest_timestamp = memories[0]["created_at"]
        
        # Merge content
        if merged_content is None:
            # Auto-merge: concatenate with separators
            merged_content = "\n\n".join([m["content"] for m in memories])
        
        # Merge tags
        if keep_all_tags:
            all_tags = set()
            for m in memories:
                all_tags.update(m["tags"])
            merged_tags = list(all_tags)
        else:
            merged_tags = memories[0]["tags"]
        
        # Create merged memory with oldest timestamp
        merged_key = f"memory_{datetime.fromisoformat(oldest_timestamp).strftime('%Y%m%d%H%M%S')}_merged"
        
        # Save to database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO memories 
                   (key, content, created_at, updated_at, tags) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    merged_key,
                    merged_content,
                    oldest_timestamp,
                    get_current_time().isoformat(),
                    json.dumps(merged_tags) if merged_tags else None
                )
            )
            conn.commit()
        
        # Update vector store
        mark_vector_store_dirty()
        
        # Delete originals if requested
        deleted_keys = []
        if delete_originals:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                for key in memory_keys:
                    cursor.execute("DELETE FROM memories WHERE key = ?", (key,))
                    deleted_keys.append(key)
                conn.commit()
        
        # Format result
        result = f"✅ Successfully merged {len(memory_keys)} memories!\n\n"
        result += f"🆕 New merged memory: [{merged_key}]\n"
        result += f"📅 Timestamp: {oldest_timestamp} (oldest)\n"
        result += f"📝 Content ({len(merged_content)} chars):\n"
        result += f"   {merged_content[:200]}{'...' if len(merged_content) > 200 else ''}\n\n"
        
        if merged_tags:
            result += f"🏷️  Tags: {', '.join(merged_tags)}\n\n"
        
        if delete_originals:
            result += f"🗑️  Deleted {len(deleted_keys)} original memories:\n"
            for key in deleted_keys:
                result += f"   - {key}\n"
        else:
            result += f"💡 Original memories kept (delete_originals=False)\n"
        
        result += f"\n💡 Persona: {persona}"
        
        _log_progress(f"✅ Merged {len(memory_keys)} memories into {merged_key}")
        return result
        
    except Exception as e:
        _log_progress(f"❌ Failed to merge memories: {e}")
        return f"❌ Error merging memories: {str(e)}"


async def analyze_sentiment(content: str) -> str:
    """
    Analyze sentiment/emotion of text using AI.
    
    **When to use this tool:**
    - Need to understand emotional tone of text
    - Determining appropriate emotion tag for memory
    - Analyzing user's emotional state from message
    - Quality checking sentiment detection
    
    **When NOT to use:**
    - Emotion is already obvious
    - Just saving memory → create_memory() handles this
    - Normal conversation flow
    
    Args:
        content: Text to analyze
        
    Returns:
        Emotion, confidence score, and details
    """
    try:
        _log_progress(f"🔍 Analyzing sentiment for text ({len(content)} chars)...")
        
        result = analyze_sentiment_text(content)
        
        if "error" in result:
            return f"❌ Error analyzing sentiment: {result.get('error', 'Unknown error')}"
        
        emotion = result.get("emotion", "neutral")
        score = result.get("score", 0.0)
        raw_label = result.get("raw_label", "unknown")
        
        # Format output
        output = "🎭 Sentiment Analysis Result:\n\n"
        output += f"📊 Detected Emotion: **{emotion}** (confidence: {score:.2%})\n"
        output += f"🏷️  Raw Label: {raw_label}\n\n"
        
        # Add emoji based on emotion
        emotion_emoji = {
            "joy": "😊",
            "sadness": "😢",
            "neutral": "😐",
            "anger": "😠",
            "fear": "😨",
            "surprise": "😲",
            "disgust": "😖"
        }
        emoji = emotion_emoji.get(emotion, "🤔")
        
        output += f"{emoji} Interpretation:\n"
        if emotion == "joy":
            output += "   The text expresses positive emotions, happiness, or satisfaction.\n"
        elif emotion == "sadness":
            output += "   The text expresses negative emotions, disappointment, or concern.\n"
        else:
            output += "   The text has a neutral or balanced emotional tone.\n"
        
        output += f"\n💡 Analyzed text ({len(content)} chars):\n"
        output += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n"
        
        _log_progress(f"✅ Sentiment analysis complete: {emotion} ({score:.2%})")
        return output
        
    except Exception as e:
        _log_progress(f"❌ Sentiment analysis failed: {e}")
        return f"❌ Error analyzing sentiment: {str(e)}"
