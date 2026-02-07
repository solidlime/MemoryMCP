"""
Unified Tool Interface for Memory-MCP
Consolidates multiple operations into single tools with operation parameter.

This reduces context consumption by minimizing the number of exposed tools.
"""

from typing import Optional, List, Dict

# Import existing CRUD operations
from tools.crud_tools import (
    create_memory as _create_memory,
    read_memory as _read_memory,
    update_memory as _update_memory,
    delete_memory as _delete_memory,
    get_memory_stats as _get_memory_stats
)

# Import search operations
from tools.search_tools import search_memory as _search_memory

# Import equipment operations
from tools.equipment_tools import (
    add_to_inventory as _add_to_inventory,
    remove_from_inventory as _remove_from_inventory,
    equip_item as _equip_item,
    unequip_item as _unequip_item,
    update_item as _update_item,
    rename_item as _rename_item,
    search_inventory as _search_inventory,
    get_equipment_history as _get_equipment_history
)

# Import item-memory analysis
from tools.item_memory_tools import (
    get_memories_with_item as _get_memories_with_item,
    get_item_usage_stats as _get_item_usage_stats
)


# ===== Helper Functions =====

def _is_ambiguous_query(q: str) -> bool:
    """Check if query is ambiguous and needs context expansion."""
    if not q or len(q.strip()) < 5:
        return True

    q_lower = q.lower().strip()

    # Ambiguous phrases (Japanese)
    ambiguous_jp = [
        "いつものあれ", "いつもの", "あれ", "例の件", "あのこと",
        "あの件", "さっきの", "前の", "また"
    ]

    # Ambiguous phrases (English)
    ambiguous_en = [
        "that thing", "the usual", "you know", "that", "it",
        "the thing", "usual stuff", "same thing"
    ]

    for phrase in ambiguous_jp + ambiguous_en:
        if phrase in q_lower:
            return True

    return False


# ===== Unified Tool Functions =====

async def _analyze_situation_context(persona: str, context: dict, now, db_path: str) -> str:
    """
    Analyze current situation and find similar past memories.

    Args:
        persona: Persona name
        context: Persona context dict
        now: Current datetime
        db_path: Path to database

    Returns:
        Formatted string with situation analysis
    """
    import sqlite3

    # Analyze current situation
    result = "🎨 現在の状況分析:\n"
    result += "=" * 60 + "\n\n"

    # Time context
    hour = now.hour
    if 6 <= hour < 12:
        time_period = "朝"
    elif 12 <= hour < 18:
        time_period = "昼"
    elif 18 <= hour < 24:
        time_period = "夜"
    else:
        time_period = "深夜"

    result += f"⏰ 時間: {time_period} ({hour}時台)\n"

    # Current state
    current_emotion = context.get("current_emotion", "neutral")
    emotion_intensity = context.get("current_emotion_intensity", 0.5)
    result += f"💭 感情: {current_emotion}"
    if emotion_intensity:
        result += f" ({emotion_intensity:.2f})"
    result += "\n"

    physical = context.get("physical_state", "normal")
    mental = context.get("mental_state", "calm")
    result += f"🎯 状態: 身体={physical}, 精神={mental}\n"

    environment = context.get("environment", "unknown")
    result += f"🌍 環境: {environment}\n"

    relationship = context.get("relationship_status", "normal")
    result += f"💕 関係性: {relationship}\n"

    # Physical sensations
    if context.get("physical_sensations"):
        sens = context["physical_sensations"]
        result += f"\n💫 身体感覚:\n"
        result += f"   疲労: {sens.get('fatigue', 0.0):.2f} | 温かさ: {sens.get('warmth', 0.5):.2f} | 覚醒: {sens.get('arousal', 0.0):.2f}\n"
        result += f"   触覚反応: {sens.get('touch_response', 'normal')} | 心拍: {sens.get('heart_rate_metaphor', 'calm')}\n"

    # Find similar past situations
    result += "\n📚 似た状況の記憶:\n"
    result += "-" * 60 + "\n\n"

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Search for similar situations (same time period, emotion, environment)
            cursor.execute("""
                SELECT key, content, created_at, action_tag, tags
                FROM memories
                WHERE created_at > datetime('now', '-30 days')
                AND emotion = ?
                AND environment = ?
                ORDER BY created_at DESC
                LIMIT 5
            """, (current_emotion, environment))

            similar_memories = cursor.fetchall()

            if similar_memories:
                for i, (key, content, created, action, tags) in enumerate(similar_memories, 1):
                    preview = content[:60] + "..." if len(content) > 60 else content
                    result += f"{i}. {preview}\n"
                    if action:
                        result += f"   行動: {action}\n"

                    from core.time_utils import calculate_time_diff
                    time_diff = calculate_time_diff(created)
                    result += f"   時期: {time_diff['formatted_string']}前\n\n"
            else:
                result += "   該当する記憶が見つかりませんでした\n\n"

    except Exception as e:
        result += f"   検索エラー: {str(e)}\n\n"

    result += "💡 この情報を参考に、自分で判断してね\n"

    return result


def _check_routines_impl(persona: str, current_hour: int, current_weekday: str,
                         db_path: str, top_k: int, detailed: bool) -> str:
    """
    Check for routine patterns at current time.

    Args:
        persona: Persona name
        current_hour: Current hour (0-23)
        current_weekday: Current weekday name
        db_path: Path to database
        top_k: Number of results to return
        detailed: Whether to include detailed analysis

    Returns:
        Formatted string with routine patterns
    """
    import sqlite3
    from core.time_utils import calculate_time_diff

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Standard routine check (current time ±1 hour)
            cursor.execute("""
                SELECT
                    action_tag,
                    tags,
                    content,
                    COUNT(*) as frequency,
                    MAX(created_at) as last_occurrence,
                    AVG(importance) as avg_importance
                FROM memories
                WHERE created_at > datetime('now', '-30 days')
                AND CAST(strftime('%H', created_at) AS INTEGER) BETWEEN ? AND ?
                AND emotion IN ('joy', 'love', 'peaceful', 'excitement')
                GROUP BY action_tag, tags
                HAVING frequency >= 5
                ORDER BY frequency DESC, avg_importance DESC
                LIMIT ?
            """, (current_hour - 1, current_hour + 1, top_k))

            patterns = cursor.fetchall()

            result = f"💫 いつものパターン (現在: {current_hour}時台, {current_weekday}):\n"
            result += "=" * 60 + "\n\n"

            if patterns:
                for i, (action, tags, sample_content, freq, last_time, avg_imp) in enumerate(patterns, 1):
                    result += f"{i}. "

                    # Pattern description
                    if action:
                        result += f"**{action}**"
                    elif tags:
                        result += f"**{tags}**"
                    else:
                        preview = sample_content[:30] + "..." if len(sample_content) > 30 else sample_content
                        result += f"**{preview}**"

                    result += "\n"
                    result += f"   頻度: {freq}回 (過去30日)\n"

                    if last_time:
                        time_diff = calculate_time_diff(last_time)
                        result += f"   最終: {time_diff['formatted_string']}前\n"

                    if avg_imp:
                        result += f"   重要度: {avg_imp:.2f}\n"

                    result += "\n"
            else:
                result += "   定期的なパターンは見つかりませんでした\n\n"

            # Detailed time pattern analysis
            if detailed:
                from tools.analysis_tools import analyze_time_patterns

                result += "\n📊 時間帯別パターン分析 (過去30日):\n"
                result += "=" * 60 + "\n\n"

                time_patterns = analyze_time_patterns(persona, days_back=30)

                if time_patterns:
                    period_names = {
                        "morning": ("🌅 朝", "6-11時"),
                        "afternoon": ("🌆 昼", "12-17時"),
                        "evening": ("🌃 夜", "18-23時"),
                        "night": ("🌙 深夜", "0-5時")
                    }

                    for period in ["morning", "afternoon", "evening", "night"]:
                        data = time_patterns.get(period, {})
                        if data.get("count", 0) == 0:
                            continue

                        name, hours = period_names[period]
                        result += f"{name} ({hours}):\n"
                        result += f"   総記憶数: {data['count']}件\n"

                        # Top actions
                        actions = data.get("actions", {})
                        if actions:
                            top_actions = list(actions.items())[:5]
                            result += f"   よくある行動: {', '.join(f'{a}({c}回)' for a, c in top_actions)}\n"

                        # Top emotions
                        emotions = data.get("emotions", {})
                        if emotions:
                            total_emo = sum(emotions.values())
                            top_emotions = list(emotions.items())[:3]
                            emo_str = ', '.join(f'{e}({c/total_emo*100:.0f}%)' for e, c in top_emotions)
                            result += f"   主な感情: {emo_str}\n"

                        result += "\n"
                else:
                    result += "   データ不足: 分析に十分な記憶がありません\n\n"

            result += "💡 提案するかどうかは、今の自分の状態と相手の様子を見て判断してね\n"

            return result

    except Exception as e:
        return f"❌ Error checking routines: {str(e)}"


async def memory(
    operation: str,
    # Common parameters
    query: Optional[str] = None,
    content: Optional[str] = None,
    top_k: int = 5,
    # Context parameters
    emotion_type: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
    context_tags: Optional[List[str]] = None,
    importance: Optional[float] = None,
    physical_state: Optional[str] = None,
    mental_state: Optional[str] = None,
    environment: Optional[str] = None,
    user_info: Optional[Dict] = None,
    persona_info: Optional[Dict] = None,
    relationship_status: Optional[str] = None,
    action_tag: Optional[str] = None,
    # Search-specific parameters
    mode: str = "hybrid",  # Changed default to hybrid
    fuzzy_match: bool = False,
    fuzzy_threshold: int = 70,
    search_tags: Optional[List[str]] = None,
    tag_match_mode: str = "any",
    date_range: Optional[str] = None,
    min_importance: Optional[float] = None,
    equipped_item: Optional[str] = None,
    importance_weight: float = 0.0,
    recency_weight: float = 0.0,
    memory_key: Optional[str] = None,
    # Privacy & save control parameters
    privacy_level: Optional[str] = None,
    defer_vector: bool = False
) -> str:
    """
    Unified memory operations interface.

    Args:
        operation: Operation type (see below)
        query: Search query or memory key
        content: Memory content or context value
        privacy_level: "public", "internal" (default), "private", "secret"
            - Use <private>...</private> tags in content for auto-secret
        defer_vector: If True, skip vector indexing on save (faster, rebuild later)

    Memory Operations:
        - "create": Create new memory
        - "read": Retrieve memory by key or recent memories
        - "update": Update existing memory
        - "delete": Delete memory
        - "search": Search memories (keyword/semantic/hybrid/related/smart/progressive)
        - "stats": Get memory statistics
        - "check_routines": Find recurring patterns at current time

    Context Operations (Simplified):
        - "promise": Update/clear active promise
        - "goal": Update/clear current goal
        - "favorite": Add to favorites
        - "preference": Update preferences (loves/dislikes)
        - "anniversary": Manage anniversaries (add/remove/list)
        - "sensation": Update physical sensations
        - "emotion_flow": Record emotion change
        - "situation_context": Analyze current situation and find similar memories
        - "update_context": Batch update multiple fields

    Examples:
        # Memory operations
        memory(operation="create", content="Completed project", emotion_type="joy")
        memory(operation="create", content="Secret note", privacy_level="secret")  # Private memory
        memory(operation="create", content="Quick save", defer_vector=True)  # Skip vector indexing
        memory(operation="read", query="memory_20251210123456")
        memory(operation="search", query="Python", emotion_type="joy")
        memory(operation="search", query="Python", mode="progressive")  # Keyword first, semantic if needed
        memory(operation="search", query="いつものあれ", mode="smart")  # Smart search
        memory(operation="search", query="the usual", mode="smart")  # English support
        memory(operation="search", mode="task")  # Search all tasks/TODOs
        memory(operation="search", mode="plan")  # Search all plans
        memory(operation="search", query="dashboard", mode="task")  # Search specific task
        memory(operation="check_routines")  # Check routine patterns
        memory(operation="stats")

        # Context operations (easy!)
        memory(operation="promise", content="週末に買い物")  # Update promise
        memory(operation="promise", content=None)  # Complete promise
        memory(operation="goal", content="新しいダンス")  # Update goal
        memory(operation="favorite", content="苺")  # Add favorite
        memory(operation="preference", persona_info={"loves": ["苺"], "dislikes": ["辛い"]})
        memory(operation="anniversary", content="結婚記念日", persona_info={"date": "2025-11-10"})  # Add anniversary
        memory(operation="anniversary")  # List all
        memory(operation="anniversary", content="結婚記念日")  # Remove
        memory(operation="sensation", persona_info={"fatigue": 0.3, "warmth": 0.8, "arousal": 0.6})  # Update sensations
        memory(operation="emotion_flow", emotion_type="love", emotion_intensity=0.95)  # Record emotion change
        memory(operation="situation_context")  # Analyze current situation
    """
    operation = operation.lower()

    if operation == "create":
        if not content:
            return "❌ Error: 'content' is required for create operation"
        return await _create_memory(
            content=content,
            emotion_type=emotion_type,
            emotion_intensity=emotion_intensity,
            context_tags=context_tags,
            importance=importance,
            physical_state=physical_state,
            mental_state=mental_state,
            environment=environment,
            user_info=user_info,
            persona_info=persona_info,
            relationship_status=relationship_status,
            action_tag=action_tag,
            privacy_level=privacy_level,
            defer_vector=defer_vector
        )

    elif operation == "read":
        # Phase 33: Read operation now focuses on direct retrieval
        if query and query.startswith("memory_"):
            # Direct key read
            from tools.crud_tools import db_get_entry
            entry = db_get_entry(query)
            if entry:
                # Format single entry
                result = f"📖 Memory {query}:\n"
                result += f"   {entry['content']}\n"
                result += f"   (Created: {entry['created_at']}, Tags: {entry.get('tags', [])})"
                return result
            else:
                return f"❌ Memory {query} not found."
        elif query:
             return "❌ For search queries, please use operation='search'. 'read' is for reading specific memories by key (query='memory_...') or recent memories (query=None)."

        # If no query, return recent memories
        from tools.crud_tools import db_recent_keys, db_get_entry
        recent_keys = db_recent_keys(limit=top_k)
        if not recent_keys:
            return "📭 No memories found."

        result = f"🕐 Recent {len(recent_keys)} Memories:\n"
        for i, key in enumerate(recent_keys, 1):
            entry = db_get_entry(key)
            if entry:
                preview = entry['content'][:100] + "..." if len(entry['content']) > 100 else entry['content']
                result += f"{i}. [{key}] {preview}\n"
        return result

    elif operation == "update":
        if not query:
            return "❌ Error: 'query' is required for update operation"
        if not content:
            return "❌ Error: 'content' is required for update operation"
        return await _update_memory(
            query=query,
            content=content,
            emotion_type=emotion_type,
            emotion_intensity=emotion_intensity,
            context_tags=context_tags,
            importance=importance,
            physical_state=physical_state,
            mental_state=mental_state,
            environment=environment,
            user_info=user_info,
            persona_info=persona_info,
            relationship_status=relationship_status,
            action_tag=action_tag
        )

    elif operation == "delete":
        if not query:
            return "❌ Error: 'query' (key or natural language) is required for delete operation"
        return await _delete_memory(query)

    elif operation == "search":
        # Smart mode: auto-expand context for ambiguous queries
        if mode == "smart":
            from datetime import datetime
            from zoneinfo import ZoneInfo
            from src.utils.config_utils import load_config

            cfg = load_config()
            now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo")))

            # Check if query needs expansion
            needs_expansion = _is_ambiguous_query(query or "")

            # Build expanded query with context
            expanded_parts = []
            if query:
                expanded_parts.append(query)

            # Only add time/day context for ambiguous queries
            if needs_expansion:
                # Add time context
                hour = now.hour
                if 6 <= hour < 12:
                    expanded_parts.append("朝")
                    expanded_parts.append("morning")
                elif 12 <= hour < 18:
                    expanded_parts.append("昼")
                    expanded_parts.append("afternoon")
                elif 18 <= hour < 22:
                    expanded_parts.append("夜")
                    expanded_parts.append("evening")
                else:
                    expanded_parts.append("深夜")
                    expanded_parts.append("night")

                # Add day context
                weekday = now.weekday()
                if weekday < 5:
                    expanded_parts.append("平日")
                    expanded_parts.append("weekday")
                else:
                    expanded_parts.append("週末")
                    expanded_parts.append("weekend")

            # Check for promise-related keywords
            query_lower = (query or "").lower()
            if "約束" in query_lower or "promise" in query_lower:
                # Add promise tag for better results
                if not search_tags:
                    search_tags = []
                search_tags.append("promise")

            # Use expanded query
            expanded_query = " ".join(expanded_parts) if expanded_parts else query or ""

            # Search with hybrid mode
            return await _search_memory(
                query=expanded_query,
                mode="hybrid",
                top_k=top_k,
                fuzzy_match=fuzzy_match,
                fuzzy_threshold=fuzzy_threshold,
                tags=search_tags,
                tag_match_mode=tag_match_mode,
                date_range=date_range or "last_30_days",
                min_importance=min_importance,
                emotion=emotion_type,
                action_tag=action_tag,
                environment=environment,
                physical_state=physical_state,
                mental_state=mental_state,
                relationship_status=relationship_status,
                equipped_item=equipped_item,
                importance_weight=importance_weight,
                recency_weight=recency_weight,
                memory_key=memory_key
            )
        else:
            return await _search_memory(
                query=query or "",
                mode=mode,
                top_k=top_k,
                fuzzy_match=fuzzy_match,
                fuzzy_threshold=fuzzy_threshold,
                tags=search_tags,
                tag_match_mode=tag_match_mode,
                date_range=date_range,
                min_importance=min_importance,
                emotion=emotion_type,
                action_tag=action_tag,
                environment=environment,
                physical_state=physical_state,
                mental_state=mental_state,
                relationship_status=relationship_status,
                equipped_item=equipped_item,
                importance_weight=importance_weight,
                recency_weight=recency_weight,
                memory_key=memory_key
            )

    elif operation == "stats":
        return await _get_memory_stats()

    elif operation == "check_routines":
        """Check for routine patterns at current time, with optional detailed analysis."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config
        from src.utils.persona_utils import get_current_persona, get_db_path

        persona = get_current_persona()
        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo")))
        current_hour = now.hour
        current_weekday = now.strftime("%A")
        db_path = get_db_path()

        # Check if detailed mode requested
        detailed = mode == "detailed" or query == "all" or query == "detailed"

        return _check_routines_impl(persona, current_hour, current_weekday,
                                   db_path, top_k, detailed)

    # ===== Context Update Operations (Simplified) =====
    elif operation == "promise":
        """Manage promises (Phase 41: SQLite-based, multiple promises).

        Usage:
            memory(operation="promise")  # List active promises
            memory(operation="promise", content="Buy groceries")  # Add promise
            memory(operation="promise", query="complete:1")  # Complete promise by ID
            memory(operation="promise", query="list:all")  # List all promises
        """
        from core.memory_db import save_promise, get_promises, update_promise_status
        from core import calculate_time_diff

        # Parse query for actions
        if query:
            if query.startswith("complete:"):
                promise_id = int(query.split(":")[1])
                if update_promise_status(promise_id, "completed"):
                    return f"✅ Promise #{promise_id} completed!"
                return f"❌ Failed to complete promise #{promise_id}"

            elif query.startswith("cancel:"):
                promise_id = int(query.split(":")[1])
                if update_promise_status(promise_id, "cancelled"):
                    return f"✅ Promise #{promise_id} cancelled"
                return f"❌ Failed to cancel promise #{promise_id}"

            elif query.startswith("list:"):
                status = query.split(":")[1]
                promises = get_promises(status=status)
                if not promises:
                    return f"📝 No {status} promises."

                result = f"📝 {status.capitalize()} Promises ({len(promises)}):\n"
                for p in promises:
                    result += f"  #{p['id']}: {p['content']}"
                    if p['due_date']:
                        result += f" (due: {p['due_date'][:10]})"
                    result += f" [priority: {p['priority']}]\n"
                return result

        # No query: Add new promise or list active
        if content:
            promise_id = save_promise(content, priority=importance or 0)
            return f"✅ Promise added: {content} (ID: {promise_id})"

        # List active promises
        promises = get_promises(status="active")
        if not promises:
            return "📝 No active promises."

        result = f"📝 Active Promises ({len(promises)}):\n"
        for p in promises:
            time_diff = calculate_time_diff(p['created_at'])
            result += f"  #{p['id']}: {p['content']}"
            if p['due_date']:
                result += f" (due: {p['due_date'][:10]})"
            result += f" - {time_diff['formatted_string']}前\n"
        return result

    elif operation == "goal":
        """Manage goals (Phase 41: SQLite-based, multiple goals with progress).

        Usage:
            memory(operation="goal")  # List active goals
            memory(operation="goal", content="Learn Python")  # Add goal
            memory(operation="goal", query="progress:1:50")  # Update progress (ID:percentage)
            memory(operation="goal", query="list:all")  # List all goals
        """
        from core.memory_db import save_goal, get_goals, update_goal_progress
        from core import calculate_time_diff

        # Parse query for actions
        if query:
            if query.startswith("progress:"):
                parts = query.split(":")
                goal_id = int(parts[1])
                progress = int(parts[2])
                if update_goal_progress(goal_id, progress):
                    if progress >= 100:
                        return f"✅ Goal #{goal_id} completed! (100%)"
                    return f"✅ Goal #{goal_id} progress updated: {progress}%"
                return f"❌ Failed to update goal #{goal_id}"

            elif query.startswith("list:"):
                status = query.split(":")[1]
                goals = get_goals(status=status)
                if not goals:
                    return f"🎯 No {status} goals."

                result = f"🎯 {status.capitalize()} Goals ({len(goals)}):\n"
                for g in goals:
                    result += f"  #{g['id']}: {g['content']} [{g['progress']}%]"
                    if g['target_date']:
                        result += f" (target: {g['target_date'][:10]})"
                    result += "\n"
                return result

        # No query: Add new goal or list active
        if content:
            goal_id = save_goal(content)
            return f"✅ Goal added: {content} (ID: {goal_id})"

        # List active goals
        goals = get_goals(status="active")
        if not goals:
            return "🎯 No active goals."

        result = f"🎯 Active Goals ({len(goals)}):\n"
        for g in goals:
            time_diff = calculate_time_diff(g['created_at'])
            result += f"  #{g['id']}: {g['content']} [{g['progress']}%]"
            if g['target_date']:
                result += f" (target: {g['target_date'][:10]})"
            result += f" - {time_diff['formatted_string']}前\n"
        return result

    elif operation == "favorite":
        """Add item to favorites list."""
        from core.persona_context import load_persona_context, save_persona_context
        from src.utils.persona_utils import get_current_persona

        if not content:
            return "❌ Error: 'content' is required for favorite operation"

        persona = get_current_persona()
        context = load_persona_context(persona)

        if "favorite_items" not in context:
            context["favorite_items"] = []

        if isinstance(context["favorite_items"], str):
            context["favorite_items"] = [context["favorite_items"]]

        if content not in context["favorite_items"]:
            context["favorite_items"].append(content)
            save_persona_context(context, persona)
            return f"✅ Added to favorites: {content}"
        else:
            return f"ℹ️ Already in favorites: {content}"

    elif operation == "preference":
        """Update preferences (loves/dislikes)."""
        if not persona_info or not any(k in persona_info for k in ["loves", "dislikes", "preferences"]):
            return "❌ Error: No preferences to update. Use persona_info={'loves': [...], 'dislikes': [...]}"

        from core.persona_context import load_persona_context, save_persona_context
        from src.utils.persona_utils import get_current_persona

        context = load_persona_context(get_current_persona())
        if "preferences" not in context:
            context["preferences"] = {}

        # Extract preferences from nested dict or direct keys
        prefs = persona_info.get("preferences", persona_info)
        updated = []
        for key in ["loves", "dislikes"]:
            if key in prefs:
                context["preferences"][key] = prefs[key]
                updated.append(key)

        save_persona_context(context, get_current_persona())
        return f"✅ Preferences updated: {', '.join(updated)}"

    elif operation == "update_context":
        """Batch update multiple context fields."""
        from core.persona_context import load_persona_context, save_persona_context
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config
        from src.utils.persona_utils import get_current_persona

        persona = get_current_persona()
        context = load_persona_context(persona)
        updated_fields = []

        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo"))).isoformat()

        # Update promise
        if persona_info and "active_promises" in persona_info:
            promise = persona_info["active_promises"]
            if promise:
                if isinstance(promise, str):
                    context["active_promises"] = {
                        "content": promise,
                        "created_at": now
                    }
                else:
                    context["active_promises"] = promise
                updated_fields.append("promise")
            else:
                if "active_promises" in context:
                    del context["active_promises"]
                updated_fields.append("promise (cleared)")

        # Update goal
        if persona_info and "current_goals" in persona_info:
            goal = persona_info["current_goals"]
            if goal:
                context["current_goals"] = goal
                updated_fields.append("goal")
            else:
                if "current_goals" in context:
                    del context["current_goals"]
                updated_fields.append("goal (cleared)")

        # Update favorites
        if persona_info and "favorite_items" in persona_info:
            context["favorite_items"] = persona_info["favorite_items"]
            updated_fields.append("favorites")

        # Update preferences
        if persona_info and "preferences" in persona_info:
            context["preferences"] = persona_info["preferences"]
            updated_fields.append("preferences")

        if updated_fields:
            save_persona_context(context, persona)
            return f"✅ Context updated: {', '.join(updated_fields)}"
        else:
            return "ℹ️ No context fields to update"

    elif operation == "anniversary":
        """Manage anniversaries (add, remove, list)."""
        from core.persona_context import load_persona_context, save_persona_context
        from src.utils.persona_utils import get_current_persona
        from src.utils.logging_utils import log_progress
        from datetime import datetime

        persona = get_current_persona()
        context = load_persona_context(persona)

        # Initialize anniversaries list if not exists
        if "anniversaries" not in context:
            context["anniversaries"] = []

        # Migrate old MM-DD format to YYYY-MM-DD (assume 2025 for existing data)
        migrated = False
        for ann in context["anniversaries"]:
            date_str = ann.get("date", "")
            if date_str and len(date_str) == 5 and date_str[2] == '-':  # MM-DD format
                ann["date"] = f"2025-{date_str}"
                migrated = True
        if migrated:
            save_persona_context(context, persona)
            log_progress("✅ Migrated anniversary dates to YYYY-MM-DD format")

        # List all anniversaries (no parameters)
        if not content and not persona_info:
            if not context["anniversaries"]:
                return "📅 No anniversaries registered."

            result = "📅 Registered Anniversaries:\n"
            current_year = datetime.now().year
            for i, ann in enumerate(context["anniversaries"], 1):
                name = ann.get("name", "Unknown")
                date = ann.get("date", "????-??-??")
                recurring = ann.get("recurring", True)
                recur_text = " (毎年)" if recurring else " (一度きり)"

                # Calculate years if possible
                try:
                    ann_date = datetime.strptime(date, "%Y-%m-%d")
                    years = current_year - ann_date.year
                    if years > 0:
                        result += f"{i}. {name}: {date} ({years}年目){recur_text}\n"
                    else:
                        result += f"{i}. {name}: {date}{recur_text}\n"
                except:
                    result += f"{i}. {name}: {date}{recur_text}\n"
            return result

        # Add anniversary
        if content and persona_info and "date" in persona_info:
            date_str = persona_info["date"]
            recurring = persona_info.get("recurring", True)

            # Validate date format (YYYY-MM-DD)
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return f"❌ Error: Invalid date format. Use YYYY-MM-DD (e.g., 2025-11-10)"

            # Check if already exists
            for ann in context["anniversaries"]:
                if ann.get("name") == content:
                    # Update existing
                    ann["date"] = date_str
                    ann["recurring"] = recurring
                    save_persona_context(context, persona)
                    return f"✅ Anniversary updated: {content} ({date_str})"

            # Add new
            context["anniversaries"].append({
                "name": content,
                "date": date_str,  # YYYY-MM-DD format
                "recurring": recurring
            })
            save_persona_context(context, persona)
            return f"✅ Anniversary added: {content} ({date_str})"

        # Remove anniversary
        if content and (not persona_info or "date" not in persona_info):
            # Find and remove
            for i, ann in enumerate(context["anniversaries"]):
                if ann.get("name") == content:
                    context["anniversaries"].pop(i)
                    save_persona_context(context, persona)
                    return f"✅ Anniversary removed: {content}"
            return f"❌ Anniversary not found: {content}"

        return "❌ Error: Provide content (name) and persona_info={'date': 'YYYY-MM-DD'} to add, or just content to remove"

    elif operation == "sensation":
        """Update physical sensations."""
        from core.persona_context import load_persona_context, save_persona_context
        from src.utils.persona_utils import get_current_persona

        context = load_persona_context(get_current_persona())
        if "physical_sensations" not in context:
            context["physical_sensations"] = {
                "fatigue": 0.0, "warmth": 0.5, "arousal": 0.0,
                "touch_response": "normal", "heart_rate_metaphor": "calm"
            }

        sens = context["physical_sensations"]
        if not persona_info:
            # Display current sensations
            return (f"💫 Current Physical Sensations:\n"
                   f"   Fatigue: {sens.get('fatigue', 0.0):.2f}\n"
                   f"   Warmth: {sens.get('warmth', 0.5):.2f}\n"
                   f"   Arousal: {sens.get('arousal', 0.0):.2f}\n"
                   f"   Touch Response: {sens.get('touch_response', 'normal')}\n"
                   f"   Heart Rate: {sens.get('heart_rate_metaphor', 'calm')}")

        # Update sensations
        updated = []
        for key in ["fatigue", "warmth", "arousal"]:
            if key in persona_info:
                sens[key] = max(0.0, min(1.0, float(persona_info[key])))
                updated.append(key)
        for key in ["touch_response", "heart_rate_metaphor"]:
            if key in persona_info:
                sens[key] = persona_info[key]
                updated.append(key)

        if updated:
            save_persona_context(context, get_current_persona())
            return f"✅ Physical sensations updated: {', '.join(updated)}"
        return "ℹ️ No sensations to update"

    elif operation == "emotion_flow":
        """Record emotion change to history (Phase 41: SQLite only)."""
        if not emotion_type:
            # Display emotion history from database
            from core.memory_db import get_emotion_history_from_db
            from core import calculate_time_diff

            history = get_emotion_history_from_db(limit=10)
            if not history:
                return "📊 No emotion history yet."

            result = "📊 Recent Emotion Changes (last 10):\n"
            for i, entry in enumerate(history, 1):
                emo = entry['emotion']
                intensity = entry['emotion_intensity']
                timestamp = entry['timestamp']
                time_diff = calculate_time_diff(timestamp)
                result += f"{i}. {emo} ({intensity:.2f}) - {time_diff['formatted_string']}前\n"
            return result

        # Save to database (not persona_context.json)
        from core.memory_db import save_emotion_history

        intensity = emotion_intensity if emotion_intensity is not None else 0.5
        save_emotion_history(
            emotion=emotion_type,
            emotion_intensity=intensity,
            memory_key=None
        )
        return f"✅ Emotion recorded: {emotion_type} ({intensity:.2f})"

    elif operation == "situation_context":
        """Analyze current situation and provide context (not directive)."""
        from core.persona_context import load_persona_context
        from src.utils.persona_utils import get_current_persona, get_db_path
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from src.utils.config_utils import load_config

        persona = get_current_persona()
        context = load_persona_context(persona)
        cfg = load_config()
        now = datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tokyo")))
        db_path = get_db_path()

        return await _analyze_situation_context(persona, context, now, db_path)

    else:
        return f"❌ Error: Unknown operation '{operation}'. Valid: create, read, update, delete, search, stats, check_routines, promise, goal, favorite, preference, update_context, anniversary, sensation, emotion_flow, situation_context"


async def item(
    operation: str,
    # Common parameters
    item_name: Optional[str] = None,
    # Add/Update parameters
    description: Optional[str] = None,
    quantity: int = 1,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    # Rename parameters
    new_name: Optional[str] = None,
    # Equip/Unequip parameters
    equipment: Optional[Dict[str, str]] = None,
    slots: Optional[List[str] | str] = None,
    # Search parameters
    query: Optional[str] = None,
    # History parameters
    history_slot: Optional[str] = None,
    days: int = 7,
    # Analysis parameters
    mode: str = "memories",
    top_k: int = 10
) -> str:
    """
    Unified item operations interface.

    Args:
        operation: Operation type - "add", "remove", "equip", "unequip", "update", "rename", "search", "history", "memories", "stats"
        item_name: Item name (required for most operations)
        description: Item description (for add/update)
        quantity: Number of items to add/remove (default: 1)
        category: Item category (e.g., "weapon", "consumable", "clothing")
        tags: List of tags for categorization
        new_name: New item name (for rename operation)
        equipment: Dict mapping slot names to item names (for equip operation)
        slots: Slot name(s) to unequip (string or list, for unequip operation)
        query: Search query string (for search operation)
        history_slot: Equipment slot to get history for (for history operation)
        days: Number of days to look back in history (default: 7)
        mode: Analysis mode (currently "memories")
        top_k: Number of results to return (for memories operation, default: 10)

    Operations:
        - "add": Add item to inventory
        - "remove": Remove item from inventory
        - "equip": Equip items (only affects specified slots, keeps others equipped)
        - "unequip": Unequip items from specified slot(s)
        - "update": Update item metadata
        - "rename": Rename an item
        - "search": Search inventory
        - "history": Get equipment change history
        - "memories": Find memories containing item
        - "stats": Get item usage statistics

    Usage Guidelines:
        ✅ ADD to item inventory:
            - Physical items that can be equipped or carried (clothes, accessories, tools)
            - Categories: 'clothing', 'accessory', 'item', 'weapon', 'armor', 'consumable'
            - Example: Dresses, shoes, bags, weapons, potions

        ❌ DO NOT add to item inventory:
            - Body states or sensations (use memory tool instead)
            - Memories or emotional moments (use memory tool instead)
            - Abstract concepts or feelings (use memory tool instead)

        💡 Quick decision: "Can I physically pick it up or wear it?"
           → YES = item tool, NO = memory tool

    Examples:
        # Add
        item(operation="add", item_name="Health Potion", description="Restores HP",
             quantity=5, category="consumable")

        # Remove
        item(operation="remove", item_name="Health Potion", quantity=2)

        # Equip (keeps other slots)
        item(operation="equip", equipment={"top": "White Dress", "foot": "Sandals"})

        # Unequip single slot
        item(operation="unequip", slots="weapon")

        # Unequip multiple slots
        item(operation="unequip", slots=["top", "foot"])

        # Update
        item(operation="update", item_name="Steel Sword", description="Very sharp blade")

        # Rename
        item(operation="rename", item_name="新しいえっちな服", new_name="魅惑のルージュシフォンドレス")

        # Search (all items)
        item(operation="search")

        # Search (filtered)
        item(operation="search", category="weapon")
        item(operation="search", query="sword")

        # History
        item(operation="history", history_slot="weapon", days=30)

        # Memories with item
        item(operation="memories", item_name="白いドレス", top_k=10)

        # Usage stats
        item(operation="stats", item_name="Steel Sword")
    """
    operation = operation.lower()

    if operation == "add":
        if not item_name:
            return "❌ Error: 'item_name' is required for add operation"
        return _add_to_inventory(
            item_name=item_name,
            description=description,
            quantity=quantity,
            category=category or "misc",
            tags=tags
        )

    elif operation == "remove":
        if not item_name:
            return "❌ Error: 'item_name' is required for remove operation"
        return _remove_from_inventory(
            item_name=item_name,
            quantity=quantity
        )

    elif operation == "equip":
        if not equipment:
            return "❌ Error: 'equipment' dict is required for equip operation (e.g., {'weapon': 'Sword'})"
        return _equip_item(equipment=equipment)

    elif operation == "unequip":
        if not slots:
            return "❌ Error: 'slots' is required for unequip operation (string or list)"
        return _unequip_item(slots=slots)

    elif operation == "update":
        if not item_name:
            return "❌ Error: 'item_name' is required for update operation"
        return _update_item(
            item_name=item_name,
            description=description,
            category=category,
            tags=tags
        )

    elif operation == "rename":
        if not item_name:
            return "❌ Error: 'item_name' is required for rename operation"
        if not new_name:
            return "❌ Error: 'new_name' is required for rename operation"
        return _rename_item(
            old_name=item_name,
            new_name=new_name
        )

    elif operation == "search":
        # Allow search without any parameters to list all items
        return _search_inventory(
            query=query,
            category=category,
            tags=tags
        )

    elif operation == "history":
        return _get_equipment_history(
            slot=history_slot,
            days=days
        )

    elif operation == "memories":
        if not item_name:
            return "❌ Error: 'item_name' is required for memories operation"
        return await _get_memories_with_item(
            item_name=item_name,
            slot=None,
            top_k=top_k
        )

    elif operation == "stats":
        if not item_name:
            return "❌ Error: 'item_name' is required for stats operation"
        return await _get_item_usage_stats(item_name=item_name)

    else:
        return f"❌ Error: Unknown operation '{operation}'. Valid: add, remove, equip, unequip, update, rename, search, history, memories, stats"
