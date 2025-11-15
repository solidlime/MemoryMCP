"""
Item-Memory Association Tools
Provides tools to find memories associated with specific items
"""

import sqlite3
import json
from typing import Optional, List
from datetime import datetime

# Core imports
from core import calculate_time_diff

# Utility imports
from src.utils.persona_utils import get_db_path, get_current_persona


async def get_memories_with_item(
    item_name: str,
    slot: Optional[str] = None,
    top_k: int = 10
) -> str:
    """
    Find all memories where a specific item was equipped.
    
    Args:
        item_name: Item name to search for (partial match)
        slot: Filter by equipment slot (optional)
        top_k: Maximum results (default: 10)
    
    Returns:
        Formatted list of memories with the item
    
    Examples:
        get_memories_with_item("白いドレス")
        get_memories_with_item("星月の祈り", slot="clothing_top")
        get_memories_with_item("ソード", slot="weapon")
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Read memories with equipped_items
        memories = []
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT key, content, created_at, equipped_items, 
                       importance, emotion, emotion_intensity, 
                       action_tag, environment
                FROM memories 
                WHERE equipped_items IS NOT NULL
                ORDER BY created_at DESC
            ''')
            
            for row in cursor.fetchall():
                key, content, created_at, equipped_items_json, importance, emotion, emotion_intensity, action_tag, environment = row
                
                # Parse equipped_items
                if not equipped_items_json:
                    continue
                
                try:
                    equipped_items = json.loads(equipped_items_json)
                except:
                    continue
                
                # Check if item matches
                matched_slots = []
                for eq_slot, eq_item in equipped_items.items():
                    if eq_item and item_name.lower() in eq_item.lower():
                        # Apply slot filter if specified
                        if slot is None or eq_slot == slot:
                            matched_slots.append((eq_slot, eq_item))
                
                # If matched, add to results
                if matched_slots:
                    memories.append({
                        'key': key,
                        'content': content,
                        'created_at': created_at,
                        'matched_slots': matched_slots,
                        'all_equipment': equipped_items,
                        'importance': importance,
                        'emotion': emotion,
                        'emotion_intensity': emotion_intensity,
                        'action_tag': action_tag,
                        'environment': environment
                    })
        
        # Limit results
        memories = memories[:top_k]
        
        if not memories:
            slot_str = f" in slot '{slot}'" if slot else ""
            return f"📭 No memories found with item '{item_name}'{slot_str}."
        
        # Format results
        slot_str = f" in slot '{slot}'" if slot else ""
        result = f"🔍 Found {len(memories)} memories with item '{item_name}'{slot_str} (persona: {persona}):\n\n"
        
        for i, mem in enumerate(memories, 1):
            key = mem['key']
            content = mem['content']
            created_at = mem['created_at']
            matched_slots = mem['matched_slots']
            all_equipment = mem['all_equipment']
            
            # Calculate time ago
            created_date = created_at[:10]
            created_time = created_at[11:19]
            time_diff = calculate_time_diff(created_at)
            time_ago = f" ({time_diff['formatted_string']}前)"
            
            # Build metadata
            meta_parts = []
            if mem['importance'] is not None and mem['importance'] != 0.5:
                meta_parts.append(f"⭐{mem['importance']:.1f}")
            if mem['emotion'] and mem['emotion'] != "neutral":
                emotion_str = f"💭{mem['emotion']}"
                if mem['emotion_intensity'] and mem['emotion_intensity'] >= 0.5:
                    emotion_str += f"({mem['emotion_intensity']:.1f})"
                meta_parts.append(emotion_str)
            if mem['action_tag']:
                meta_parts.append(f"🎭{mem['action_tag']}")
            if mem['environment'] and mem['environment'] != "unknown":
                meta_parts.append(f"📍{mem['environment']}")
            
            meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""
            
            result += f"{i}. [{key}]{meta_str}\n"
            result += f"   {content[:200]}{'...' if len(content) > 200 else ''}\n"
            result += f"   {created_date} {created_time}{time_ago}\n"
            
            # Show matched slots
            result += f"   👗 Matched: "
            result += ", ".join([f"{slot}={item}" for slot, item in matched_slots])
            result += "\n"
            
            # Show all equipment if more than matched
            if len(all_equipment) > len(matched_slots):
                other_items = {k: v for k, v in all_equipment.items() if (k, v) not in matched_slots}
                if other_items:
                    result += f"   ⚔️ Other: "
                    result += ", ".join([f"{s}={i}" for s, i in other_items.items()])
                    result += "\n"
            
            result += "\n"
        
        return result.rstrip()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Failed to search memories by item: {str(e)}"


async def get_item_usage_stats(item_name: str) -> str:
    """
    Get statistics about item usage in memories.
    
    Args:
        item_name: Item name to analyze (partial match)
    
    Returns:
        Statistics about when and how the item was used
    
    Examples:
        get_item_usage_stats("白いドレス")
        get_item_usage_stats("星月の祈り")
    """
    try:
        persona = get_current_persona()
        db_path = get_db_path()
        
        # Collect all usages
        usages = []
        slot_counts = {}
        emotion_counts = {}
        action_counts = {}
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT created_at, equipped_items, emotion, action_tag
                FROM memories 
                WHERE equipped_items IS NOT NULL
                ORDER BY created_at DESC
            ''')
            
            for row in cursor.fetchall():
                created_at, equipped_items_json, emotion, action_tag = row
                
                if not equipped_items_json:
                    continue
                
                try:
                    equipped_items = json.loads(equipped_items_json)
                except (json.JSONDecodeError, TypeError):
                    continue
                
                # Check if item matches
                for slot, eq_item in equipped_items.items():
                    if eq_item and item_name.lower() in eq_item.lower():
                        usages.append({
                            'date': created_at[:10],
                            'slot': slot,
                            'emotion': emotion,
                            'action': action_tag
                        })
                        
                        # Count by slot
                        slot_counts[slot] = slot_counts.get(slot, 0) + 1
                        
                        # Count by emotion
                        if emotion:
                            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                        
                        # Count by action
                        if action_tag:
                            action_counts[action_tag] = action_counts.get(action_tag, 0) + 1
        
        if not usages:
            return f"📭 No usage data found for item '{item_name}'."
        
        # Format results
        result = f"📊 Usage statistics for '{item_name}' (persona: {persona}):\n\n"
        result += f"Total usages: {len(usages)}\n"
        result += f"First used: {usages[-1]['date']}\n"
        result += f"Last used: {usages[0]['date']}\n\n"
        
        # Slot distribution
        result += "Equipment slots:\n"
        for slot, count in sorted(slot_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(usages)) * 100
            result += f"  • {slot}: {count} times ({percentage:.1f}%)\n"
        
        # Emotion distribution
        if emotion_counts:
            result += "\nEmotions when wearing:\n"
            for emotion, count in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(usages)) * 100
                result += f"  • {emotion}: {count} times ({percentage:.1f}%)\n"
        
        # Action distribution
        if action_counts:
            result += "\nActivities when wearing:\n"
            for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(usages)) * 100
                result += f"  • {action}: {count} times ({percentage:.1f}%)\n"
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Failed to get item usage stats: {str(e)}"
