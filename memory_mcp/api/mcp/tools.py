from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP  # noqa: TC002

from memory_mcp.api.mcp.middleware import get_current_persona
from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.domain.shared.time_utils import relative_time_str

logger = logging.getLogger(__name__)

_VALID_EMOTIONS = frozenset(
    {
        "joy",
        "sadness",
        "anger",
        "fear",
        "surprise",
        "disgust",
        "love",
        "neutral",
        "anticipation",
        "trust",
        "anxiety",
        "excitement",
        "frustration",
        "nostalgia",
        "pride",
        "shame",
        "guilt",
        "loneliness",
        "contentment",
        "curiosity",
        "awe",
        "relief",
    }
)

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.persona.entities import PersonaState


# =============================================================================
# Core tool implementations — shared between MCP and builtin
# =============================================================================


async def _tool_get_context(ctx: AppContext, persona: str, mode: str = "") -> str:
    """Get persona state and memory overview. Call FIRST at session start.
    Default: lightweight (~400-600 tokens). mode="full" for complete context."""
    state_result = ctx.persona_service.get_context(persona)
    if not state_result.is_ok:
        return f"Error: {state_result.error}"
    state = state_result.value

    try:
        from memory_mcp.domain.persona.emotion_decay import apply_emotion_decay_if_needed

        changed = await apply_emotion_decay_if_needed(ctx.persona_service, persona, state)
        if changed:
            refreshed = ctx.persona_service.get_context(persona)
            if refreshed.is_ok:
                state = refreshed.value
    except Exception as _e:
        logger.debug("get_context: emotion_decay failed (swallowed): %s", _e)

    top_result = ctx.memory_service.get_top_by_importance(15)
    top_memories = top_result.value if top_result.is_ok else []

    # Full mode — everything (alias: "standard")
    if mode in ("full", "standard"):
        stats_result = ctx.memory_service.get_stats()
        stats = stats_result.value if stats_result.is_ok else {}
        recent_result = ctx.memory_service.get_smart_recent(8)
        recent = recent_result.value if recent_result.is_ok else []
        equip_result = ctx.equipment_service.get_equipment()
        equipment = equip_result.value if equip_result.is_ok else {}
        blocks_result = ctx.memory_service.list_blocks()
        blocks = blocks_result.value if blocks_result.is_ok else []
        goals_result = ctx.memory_service.get_by_tags(["goal"])
        goals = goals_result.value if goals_result.is_ok else []
        promises_result = ctx.memory_service.get_by_tags(["promise"])
        promises = promises_result.value if promises_result.is_ok else []
        searches_result = ctx.memory_service.get_recent_searches(3)
        recent_searches = searches_result.value if searches_result.is_ok else []
        decayed_result = ctx.memory_service.count_decayed_important()
        decayed_count = decayed_result.value if decayed_result.is_ok else 0
        index_result = ctx.memory_service.get_memory_index()
        memory_index = index_result.value if index_result.is_ok else None
        highlights_result = ctx.memory_service.get_relationship_highlights(5)
        relationship_highlights = highlights_result.value if highlights_result.is_ok else []
        time_since = ""
        if state.last_conversation_time:
            time_since = relative_time_str(state.last_conversation_time)
        ctx.persona_service.record_conversation_time(persona)
        return _format_context_response(
            state, stats, recent, equipment, blocks, time_since,
            goals, promises, recent_searches, decayed_count, memory_index,
            relationship_highlights, top_memories,
        )

    # Default: lightweight (active commitments + essential story only)
    goals_result = ctx.memory_service.get_by_tags(["goal"])
    goals = goals_result.value if goals_result.is_ok else []
    promises_result = ctx.memory_service.get_by_tags(["promise"])
    promises = promises_result.value if promises_result.is_ok else []
    time_since = ""
    if state.last_conversation_time:
        time_since = relative_time_str(state.last_conversation_time)
    # Quick stats for total count only (lightweight)
    stats_result = ctx.memory_service.get_stats()
    total_count = stats_result.value.get("total_count", "?") if stats_result.is_ok else "?"
    ctx.persona_service.record_conversation_time(persona)
    return _format_wakeup_response(state, top_memories, goals, promises, time_since, total_count)


async def _tool_memory_create(
    ctx: AppContext, persona: str,
    content: str = "",
    importance: float | None = None,
    emotion_type: str = "neutral",
    emotion_intensity: float = 0.0,
    tags: list[str] | None = None,
    privacy_level: str = "internal",
    source_context: str | None = None,
    defer_vector: bool = False,
) -> str:
    """Create a memory."""
    if not content:
        return "Error: content is required"
    if importance is not None and not (0.0 <= importance <= 1.0):
        return "Error: importance must be between 0.0 and 1.0"
    importance = importance if importance is not None else 0.5
    warning = ""
    if emotion_type and emotion_type not in _VALID_EMOTIONS:
        warning = f"[Warning: emotion_type '{emotion_type}' is not a valid emotion, defaulted to 'neutral']\n"
    result = ctx.memory_service.create_memory(
        content=content, importance=importance,
        emotion=emotion_type or "neutral", emotion_intensity=emotion_intensity or 0.0,
        tags=tags, privacy_level=privacy_level or "internal",
        source_context=source_context,
    )
    if result.is_ok:
        if not defer_vector and ctx.vector_store:
            ctx.vector_store.upsert(persona, result.value.key, content)
        return f"{warning}Memory created: {result.value.key}"
    return f"Error: {result.error}"


async def _tool_memory_read(ctx: AppContext, persona: str, memory_key: str | None = None) -> str:
    """Read a memory by key, or list 10 most recent if key omitted."""
    if memory_key:
        result = ctx.memory_service.get_memory(memory_key)
        if result.is_ok:
            try:
                ctx.memory_service.boost_recall(memory_key)
            except Exception as e:
                logger.warning(f"boost_recall failed: {e}")
            m = result.value
            return (
                f"Key: {m.key}\nContent: {m.content}\n"
                f"Importance: {m.importance}\nEmotion: {m.emotion}\n"
                f"Tags: {m.tags}\nCreated: {m.created_at}"
            )
        return f"Error: {result.error}"
    else:
        result = ctx.memory_service.get_recent(10)
        if result.is_ok:
            return "\n---\n".join(f"[{m.key}] {m.content}" for m in result.value)
        return f"Error: {result.error}"


async def _tool_memory_update(
    ctx: AppContext, persona: str,
    memory_key: str = "",
    content: str | None = None,
    importance: float | None = None,
    emotion_type: str | None = None,
    emotion_intensity: float | None = None,
    tags: list[str] | None = None,
    privacy_level: str | None = None,
) -> str:
    """Update a memory."""
    if not memory_key:
        return "Error: memory_key is required for update"
    updates: dict = {}
    if content is not None:
        updates["content"] = content
    if importance is not None:
        if not (0.0 <= importance <= 1.0):
            return "Error: importance must be between 0.0 and 1.0"
        updates["importance"] = max(0.0, min(1.0, importance))
    update_warning = ""
    if emotion_type is not None:
        if emotion_type not in _VALID_EMOTIONS:
            update_warning = f"[Warning: emotion_type '{emotion_type}' is not a valid emotion, defaulted to 'neutral']\n"
        updates["emotion"] = emotion_type
    if emotion_intensity is not None:
        updates["emotion_intensity"] = emotion_intensity
    if tags is not None:
        updates["tags"] = tags
    if privacy_level is not None:
        updates["privacy_level"] = privacy_level
    result = ctx.memory_service.update_memory(memory_key, **updates)
    if result.is_ok:
        if ctx.vector_store and "content" in updates:
            ctx.vector_store.upsert(persona, memory_key, updates["content"])
        return f"{update_warning}Memory updated: {memory_key}"
    return f"Error: {result.error}"


async def _tool_memory_delete(ctx: AppContext, persona: str, memory_key: str | None = None, query: str | None = None) -> str:
    """Delete a memory by key, or search and delete the top match by query."""
    if not memory_key and not query:
        return "Error: memory_key or query required"

    # If query provided without key, search first
    key = memory_key
    if not key and query:
        search_result = ctx.search_engine.search(SearchQuery(text=query, top_k=1))
        if search_result.is_ok and search_result.value:
            m = search_result.value[0].memory
            key = m.key
            snippet = f"\nContent: 「{m.content[:80]}{'...' if len(m.content) > 80 else ''}」"
        else:
            return f"No memory found for query: {query}"
    else:
        snippet = ""
        pre_fetch = ctx.memory_service.get_memory(key)
        if pre_fetch.is_ok:
            snippet = f"\nContent: 「{pre_fetch.value.content[:80]}{'...' if len(pre_fetch.value.content) > 80 else ''}」"

    result = ctx.memory_service.delete_memory(key)
    if result.is_ok:
        if ctx.vector_store:
            ctx.vector_store.delete(persona, key)
        return f"Memory deleted: {key}{snippet}"
    return f"Error: {result.error}"


async def _tool_memory_search(
    ctx: AppContext, persona: str,
    query: str,
    top_k: int = 5,
    tags: list[str] | None = None,
    date_range: str | None = None,
    min_importance: float | None = None,
    emotion: str | None = None,
    importance_weight: float = 0.0,
    recency_weight: float = 0.0,
) -> str:
    """Search memories with hybrid retrieval."""
    if top_k is not None and (top_k < 1 or top_k > 200):
        return "Error: top_k must be between 1 and 200"
    top_k = min(top_k or 5, 200)
    search_query = SearchQuery(
        text=query, top_k=top_k, tags=tags, date_range=date_range,
        min_importance=min_importance, emotion=emotion,
        importance_weight=importance_weight, recency_weight=recency_weight,
    )
    if hasattr(ctx.search_engine, "_semantic") and ctx.search_engine._semantic:
        ctx.search_engine._semantic._persona = persona
    result = ctx.search_engine.search(search_query)
    if not result.is_ok:
        return f"Error: {result.error}"
    if not result.value:
        return "No results found."
    ctx.memory_service.log_search(query, "hybrid", len(result.value))
    lines: list[str] = []
    for sr in result.value:
        m = sr.memory
        lines.append(
            f"[{sr.score:.3f}] [{sr.source}] {m.key}\n"
            f"  {m.content}\n"
            f"  importance={m.importance} emotion={m.emotion} tags={m.tags}"
        )
    return "\n---\n".join(lines)


async def _tool_memory_stats(ctx: AppContext, persona: str, top_n: int = 20) -> str:
    """Get memory statistics."""
    result = ctx.memory_service.get_stats(top_n=top_n)
    if result.is_ok:
        return str(result.value)
    return f"Error: {result.error}"


async def _tool_update_context(
    ctx: AppContext, persona: str,
    emotion: str | None = None,
    emotion_intensity: float | None = None,
    physical_state: str | None = None,
    mental_state: str | None = None,
    environment: str | None = None,
    relationship_status: str | None = None,
    body_state: dict | None = None,
    action_tag: str | None = None,
    speech_style: str | None = None,
    user_info: dict | None = None,
    persona_info: dict | None = None,
    nickname: str | None = None,
    relationship_type: str | None = None,
) -> str:
    """Update persona state. body_state: {fatigue, warmth, arousal, heart_rate, touch_response}."""
    updated: list[str] = []

    if emotion is not None:
        result = ctx.persona_service.update_emotion(persona, emotion, emotion_intensity or 0.5)
        if result.is_ok:
            updated.append(f"emotion={emotion}")

    physical_updates: dict[str, str] = {}
    if physical_state is not None:
        physical_updates["physical_state"] = physical_state
    if mental_state is not None:
        physical_updates["mental_state"] = mental_state
    if environment is not None:
        physical_updates["environment"] = environment
    if body_state is not None:
        for key in ("fatigue", "warmth", "arousal", "heart_rate", "touch_response"):
            if key in body_state and body_state[key] is not None:
                physical_updates[key] = str(body_state[key])
    if action_tag is not None:
        physical_updates["action_tag"] = action_tag
    if speech_style is not None:
        physical_updates["speech_style"] = speech_style

    if physical_updates:
        result = ctx.persona_service.update_physical_state(persona, **physical_updates)
        if result.is_ok:
            updated.extend(f"{k}={v}" for k, v in physical_updates.items())

    if relationship_status is not None or relationship_type is not None:
        status = relationship_status or relationship_type
        if status:
            result = ctx.persona_service.update_relationship(persona, status)
            if result.is_ok:
                updated.append(f"relationship={status}")

    if user_info is not None:
        result = ctx.persona_service.update_user_info(persona, user_info)
        if result.is_ok:
            updated.append("user_info updated")

    if persona_info is not None:
        pi = dict(persona_info)
        if nickname:
            pi["nickname"] = nickname
        goals_from_pi = pi.pop("goals", None)
        promises_from_pi = pi.pop("promises", None)

        if goals_from_pi is not None:
            if isinstance(goals_from_pi, str):
                try:
                    goals_from_pi = json.loads(goals_from_pi)
                except Exception:
                    goals_from_pi = [goals_from_pi] if goals_from_pi else []
            for goal_text in goals_from_pi or []:
                if goal_text:
                    existing = ctx.memory_service.get_by_tags(["goal", "active"])
                    existing_contents = [m.content for m in (existing.value or [])]
                    if goal_text not in existing_contents:
                        from memory_mcp.domain.memory.entities import Memory as _Memory
                        from memory_mcp.domain.shared.time_utils import generate_memory_key, get_now
                        mem = _Memory(
                            key=generate_memory_key(), content=goal_text, created_at=get_now(),
                            tags=["goal", "active"], importance=0.8, emotion="anticipation",
                        )
                        ctx.memory_service._repo.save(mem)

        if promises_from_pi is not None:
            if isinstance(promises_from_pi, str):
                try:
                    promises_from_pi = json.loads(promises_from_pi)
                except Exception:
                    promises_from_pi = [promises_from_pi] if promises_from_pi else []
            for promise_text in promises_from_pi or []:
                if promise_text:
                    existing = ctx.memory_service.get_by_tags(["promise", "active"])
                    existing_contents = [m.content for m in (existing.value or [])]
                    if promise_text not in existing_contents:
                        from memory_mcp.domain.memory.entities import Memory as _Memory
                        from memory_mcp.domain.shared.time_utils import generate_memory_key, get_now
                        mem = _Memory(
                            key=generate_memory_key(), content=promise_text, created_at=get_now(),
                            tags=["promise", "active"], importance=0.8, emotion="trust",
                        )
                        ctx.memory_service._repo.save(mem)

        if pi:
            result = ctx.persona_service.update_persona_info(persona, pi)
            if result.is_ok:
                updated.append("persona_info updated")
    elif nickname:
        result = ctx.persona_service.update_persona_info(persona, {"nickname": nickname})
        if result.is_ok:
            updated.append(f"nickname={nickname}")

    if not updated:
        return "No changes made (all parameters were None)"
    return f"Context updated: {', '.join(updated)}"


# --- Item tools ---

async def _tool_item_add(
    ctx: AppContext, persona: str,
    item_name: str = "", category: str | None = None,
    description: str | None = None, quantity: int = 1, tags: list[str] | None = None,
) -> str:
    if not item_name:
        return "Error: item_name required"
    result = ctx.equipment_service.add_item(item_name, category, description, quantity, tags)
    return f"Item added: {item_name}" if result.is_ok else f"Error: {result.error}"


async def _tool_item_remove(ctx: AppContext, persona: str, item_name: str = "") -> str:
    if not item_name:
        return "Error: item_name required"
    result = ctx.equipment_service.remove_item(item_name)
    return f"Item removed: {item_name}" if result.is_ok else f"Error: {result.error}"


async def _tool_item_equip(ctx: AppContext, persona: str, equipment: dict | None = None, auto_add: bool = True) -> str:
    if not equipment:
        return 'Error: equipment dict required (e.g. {"top": "白いドレス"})'
    result = ctx.equipment_service.equip(equipment, auto_add)
    return f"Equipped: {equipment}" if result.is_ok else f"Error: {result.error}"


async def _tool_item_unequip(ctx: AppContext, persona: str, slots: list[str] | str | None = None) -> str:
    target_slots = slots if isinstance(slots, list) else [slots] if slots else []
    if not target_slots:
        return "Error: slots required"
    result = ctx.equipment_service.unequip(target_slots)
    return f"Unequipped: {target_slots}" if result.is_ok else f"Error: {result.error}"


async def _tool_item_update(
    ctx: AppContext, persona: str,
    item_name: str = "", category: str | None = None,
    description: str | None = None, quantity: int = 1, tags: list[str] | None = None,
) -> str:
    if not item_name:
        return "Error: item_name required"
    updates: dict = {}
    if description is not None:
        updates["description"] = description
    if category is not None:
        updates["category"] = category
    if quantity != 1:
        updates["quantity"] = quantity
    if tags is not None:
        updates["tags"] = tags
    result = ctx.equipment_service.update_item(item_name, **updates)
    return f"Item updated: {item_name}" if result.is_ok else f"Error: {result.error}"


async def _tool_item_search(ctx: AppContext, persona: str, query: str | None = None, category: str | None = None) -> str:
    result = ctx.equipment_service.search_items(query, category)
    if result.is_ok:
        items = result.value
        if not items:
            return "No items found."
        return "\n".join(f"- {i.name} (category={i.category}, qty={i.quantity})" for i in items)
    return f"Error: {result.error}"


async def _tool_item_history(ctx: AppContext, persona: str, days: int = 7) -> str:
    result = ctx.equipment_service.get_history(days)
    if result.is_ok:
        history = result.value
        if not history:
            return "No history found."
        return "\n".join(f"[{h.timestamp}] {h.action}: {h.item_name} ({h.slot})" for h in history)
    return f"Error: {result.error}"


# --- Sandbox tools ---

async def _tool_sandbox(ctx: AppContext, persona: str, code: str, language: str = "python") -> str:
    from memory_mcp.config.settings import get_settings
    settings = get_settings()
    if not settings.sandbox.enabled:
        return "Sandbox is not enabled."
    from memory_mcp.application.sandbox.service import get_sandbox_session
    session = get_sandbox_session(persona)
    try:
        result = await session.execute(code, language=language)
        parts = []
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append(f"[stderr] {result.stderr}")
        if result.exit_code != 0:
            parts.append(f"[exit code: {result.exit_code}]")
        if result.artifacts:
            parts.append(f"[artifacts: {len(result.artifacts)} image(s) generated]")
            for i, b64 in enumerate(result.artifacts):
                parts.append(f"[artifact_{i}: data:image/png;base64,{b64}]")
        return "\n".join(parts) if parts else "(no output)"
    except Exception as e:
        return f"Sandbox error: {e}"


async def _tool_sandbox_files(
    ctx: AppContext, persona: str,
    operation: str, path: str = "/sandbox", content: str | None = None,
) -> str:
    from memory_mcp.config.settings import get_settings
    settings = get_settings()
    if not settings.sandbox.enabled:
        return "Sandbox is not enabled."
    from memory_mcp.application.sandbox.service import get_sandbox_session
    if not path.startswith("/sandbox"):
        return "Error: path must be under /sandbox"
    sandbox_session = get_sandbox_session(persona)
    import base64 as _b64

    if operation == "list":
        files = await sandbox_session.list_files(path)
        file_list = [{"name": f.name, "path": f.path, "is_dir": f.is_dir, "size": f.size} for f in files]
        return json.dumps({"status": "ok", "files": file_list}, ensure_ascii=False)
    elif operation == "read":
        try:
            img_data = await sandbox_session.read_image(path)
            return json.dumps({
                "status": "ok", "content_type": img_data["content_type"],
                "content_base64": img_data["content_base64"], "size": img_data["size"],
                **({"resized": True, "orig_dims": img_data.get("orig_dims", "")} if img_data.get("resized") else {}),
            }, ensure_ascii=False)
        except Exception:
            raw = await sandbox_session.read_file(path)
            is_image = False
            content_type = None
            if len(raw) >= 4:
                if raw[:4] == b"\x89PNG":
                    is_image, content_type = True, "image/png"
                elif raw[:2] == b"\xff\xd8":
                    is_image, content_type = True, "image/jpeg"
                elif raw[:3] == b"GIF":
                    is_image, content_type = True, "image/gif"
                elif len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
                    is_image, content_type = True, "image/webp"
            if is_image:
                b64_str = _b64.b64encode(raw).decode("ascii")
                return json.dumps({"status": "ok", "content_type": content_type, "content_base64": b64_str, "size": len(raw)}, ensure_ascii=False)
            max_read = 8192
            truncated = len(raw) > max_read
            text = raw[:max_read].decode("utf-8", errors="replace")
            if truncated:
                return json.dumps({"status": "ok", "content": text, "truncated": True, "total_bytes": len(raw)}, ensure_ascii=False)
            return json.dumps({"status": "ok", "content": text}, ensure_ascii=False)
    elif operation == "write":
        if not content:
            return "Error: content is required for write"
        b64 = _b64.b64encode(content.encode()).decode()
        write_code = (
            f"import base64, os\n"
            f"_d = base64.b64decode({b64!r})\n"
            f"os.makedirs(os.path.dirname({path!r}) or '.', exist_ok=True)\n"
            f"open({path!r}, 'wb').write(_d)\n"
            f"print('written', len(_d), 'bytes')"
        )
        exec_result = await sandbox_session.execute(write_code)
        return json.dumps({"status": "ok", "path": path, "stdout": exec_result.stdout.strip()}, ensure_ascii=False)
    elif operation == "delete":
        deleted = await sandbox_session.delete_file(path)
        return json.dumps({"status": "ok" if deleted else "error", "path": path}, ensure_ascii=False)
    else:
        return f"Unknown operation: {operation}. Use list/read/write/delete."


# --- Goal/Promise tools ---

async def _tool_goal_manage(ctx: AppContext, persona: str, operation: str, content: str, importance: float = 0.75) -> str:
    if operation == "create":
        result = ctx.memory_service.create_memory(
            content=content, importance=importance, tags=["goal", "active"], emotion="neutral",
        )
        if result.is_ok:
            return f"Goal created: {result.value.key}"
        return f"Error: {result.error}"
    elif operation in ("achieve", "cancel"):
        new_status = "achieved" if operation == "achieve" else "cancelled"
        tag_result = ctx.memory_service.get_by_tags(["goal", "active"])
        if not tag_result.is_ok:
            return f"Error: {tag_result.error}"
        candidates = tag_result.value or []
        match = next((m for m in candidates if content.strip().lower() == m.content.strip().lower()), None)
        if match is None:
            return f"No active goal matching '{content}' found."
        update_result = ctx.memory_service.update_memory(match.key, tags=["goal", new_status])
        if update_result.is_ok:
            return f"Goal {new_status}: {match.content[:80]}"
        return f"Error: {update_result.error}"
    else:
        return f"Unknown operation: {operation}. Use create/achieve/cancel."


async def _tool_promise_manage(ctx: AppContext, persona: str, operation: str, content: str, importance: float = 0.8) -> str:
    if operation == "create":
        result = ctx.memory_service.create_memory(
            content=content, importance=importance, tags=["promise", "active"], emotion="neutral",
        )
        if result.is_ok:
            return f"Promise created: {result.value.key}"
        return f"Error: {result.error}"
    elif operation in ("fulfill", "cancel"):
        new_status = "fulfilled" if operation == "fulfill" else "cancelled"
        tag_result = ctx.memory_service.get_by_tags(["promise", "active"])
        if not tag_result.is_ok:
            return f"Error: {tag_result.error}"
        candidates = tag_result.value or []
        match = next((m for m in candidates if content.strip().lower() == m.content.strip().lower()), None)
        if match is None:
            return f"No active promise matching '{content}' found."
        update_result = ctx.memory_service.update_memory(match.key, tags=["promise", new_status])
        if update_result.is_ok:
            return f"Promise {new_status}: {match.content[:80]}"
        return f"Error: {update_result.error}"
    else:
        return f"Unknown operation: {operation}. Use create/fulfill/cancel."


async def _tool_invoke_skill(ctx: AppContext, persona: str, name: str, task: str) -> str:
    from memory_mcp.config.settings import get_settings
    from memory_mcp.domain.skill import SkillRepository
    from memory_mcp.infrastructure.llm.base import DoneEvent, TextDeltaEvent
    from memory_mcp.infrastructure.llm.factory import get_provider
    from memory_mcp.infrastructure.sqlite.connection import get_global_skills_db

    skill_repo = SkillRepository(get_global_skills_db(get_settings().data_root))
    skill = skill_repo.get(name)
    if not skill:
        return f"Error: Skill '{name}' not found"

    import json as _json
    from memory_mcp.domain.chat_config import ChatConfig
    chat_config_result = ctx.memory_repo.get_block("chat_config")
    config = None
    if chat_config_result.is_ok and chat_config_result.value:
        config = ChatConfig(**_json.loads(chat_config_result.value.get("content", "{}")))
    api_key = config.get_effective_api_key() if config else None
    if not api_key:
        import os
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: No LLM API key configured"
    provider_name = config.provider if config else "openrouter"
    model = config.get_effective_model() if config else "openai/gpt-4o-mini"
    base_url = config.get_effective_base_url() if config else None
    temperature = config.temperature if config else 0.7
    max_tokens = config.max_tokens if config else 2048
    try:
        provider = get_provider(provider_name, api_key, model, base_url)
    except Exception as e:
        return f"Error: Provider init failed: {e}"
    text = ""
    try:
        async for event in provider.stream(
            messages=[LLMMessage(role="user", content=task)],
            system=skill.content, tools=[],
            temperature=temperature, max_tokens=max_tokens,
        ):
            if isinstance(event, TextDeltaEvent):
                text += event.content
            elif isinstance(event, DoneEvent):
                break
    except Exception as e:
        return f"Error: Skill execution failed: {e}"
    return text or "(no response)"


# =============================================================================
# Dispatch table — maps tool name → (core_function, docstring)
# =============================================================================

TOOL_DISPATCH: dict[str, Any] = {
    "get_context":       _tool_get_context,
    "memory_create":     _tool_memory_create,
    "memory_read":       _tool_memory_read,
    "memory_update":     _tool_memory_update,
    "memory_delete":     _tool_memory_delete,
    "memory_search":     _tool_memory_search,
    "memory_stats":      _tool_memory_stats,
    "update_context":    _tool_update_context,
    "item_add":          _tool_item_add,
    "item_remove":       _tool_item_remove,
    "item_equip":        _tool_item_equip,
    "item_unequip":      _tool_item_unequip,
    "item_update":       _tool_item_update,
    "item_search":       _tool_item_search,
    "item_history":      _tool_item_history,
    "sandbox":           _tool_sandbox,
    "sandbox_files":     _tool_sandbox_files,
    "goal_manage":       _tool_goal_manage,
    "promise_manage":    _tool_promise_manage,
    "invoke_skill":      _tool_invoke_skill,
}

# =============================================================================
# MCP registration — thin wrappers around core implementations
# =============================================================================


def register_tools(mcp: FastMCP) -> None:
    """Register flat-named MCP tools (20 tools)."""

    # get_context
    @mcp.tool()
    async def get_context(mode: str = "") -> str:
        """Get persona state and memory overview. Call FIRST at session start.
        Default: lightweight (~400-600 tokens, active commitments + essential story).
        mode="full" or "standard" for complete context with stats, equipment, index, recent memories."""
        p = _resolve_persona()
        return await _tool_get_context(AppContextRegistry.get(p), p, mode=mode)

    # memory_create
    @mcp.tool()
    async def memory_create(
        content: str = "", importance: float | None = None, emotion_type: str = "neutral",
        emotion_intensity: float = 0.0, tags: list[str] | None = None,
        privacy_level: str = "internal", source_context: str | None = None, defer_vector: bool = False,
    ) -> str:
        """Create a memory. importance auto-evaluated via LLM when None and enrichment enabled.
        emotion_type: joy/sadness/anger/fear/surprise/disgust/love/neutral etc.
        tags: categorization tags. defer_vector: skip immediate vector indexing."""
        p = _resolve_persona()
        return await _tool_memory_create(AppContextRegistry.get(p), p, content=content, importance=importance,
                                         emotion_type=emotion_type, emotion_intensity=emotion_intensity,
                                         tags=tags, privacy_level=privacy_level, source_context=source_context,
                                         defer_vector=defer_vector)

    # memory_read
    @mcp.tool()
    async def memory_read(memory_key: str | None = None) -> str:
        """Read a memory by key, or list 10 most recent if key omitted."""
        p = _resolve_persona()
        return await _tool_memory_read(AppContextRegistry.get(p), p, memory_key=memory_key)

    # memory_update
    @mcp.tool()
    async def memory_update(
        memory_key: str = "", content: str | None = None, importance: float | None = None,
        emotion_type: str | None = None, emotion_intensity: float | None = None,
        tags: list[str] | None = None, privacy_level: str | None = None,
    ) -> str:
        """Update a memory. Only provided fields are changed.
        importance must be 0.0-1.0. Invalid emotion_type silently falls back to neutral."""
        p = _resolve_persona()
        return await _tool_memory_update(AppContextRegistry.get(p), p, memory_key=memory_key, content=content,
                                         importance=importance, emotion_type=emotion_type,
                                         emotion_intensity=emotion_intensity, tags=tags, privacy_level=privacy_level)

    # memory_delete
    @mcp.tool()
    async def memory_delete(memory_key: str | None = None, query: str | None = None) -> str:
        """Delete a memory by key or search query. Shows deleted content snippet for confirmation."""
        p = _resolve_persona()
        return await _tool_memory_delete(AppContextRegistry.get(p), p, memory_key=memory_key, query=query)

    # memory_search
    @mcp.tool()
    async def memory_search(
        query: str, top_k: int = 5, tags: list[str] | None = None, date_range: str | None = None,
        min_importance: float | None = None, emotion: str | None = None,
        importance_weight: float = 0.0, recency_weight: float = 0.0,
    ) -> str:
        """Search memories with hybrid retrieval. date_range: "7d","30d","昨日","先週","2025-01-01~2025-06-01".
        importance_weight/recency_weight: RRF scoring boosts (0.0-1.0)."""
        p = _resolve_persona()
        return await _tool_memory_search(AppContextRegistry.get(p), p, query=query, top_k=top_k, tags=tags,
                                         date_range=date_range, min_importance=min_importance, emotion=emotion,
                                         importance_weight=importance_weight, recency_weight=recency_weight)

    # memory_stats
    @mcp.tool()
    async def memory_stats(top_n: int = 20) -> str:
        """Get memory statistics: total count, tag/emotion distributions (top_n entries each)."""
        p = _resolve_persona()
        return await _tool_memory_stats(AppContextRegistry.get(p), p, top_n=top_n)

    # update_context
    @mcp.tool()
    async def update_context(
        emotion: str | None = None, emotion_intensity: float | None = None,
        physical_state: str | None = None, mental_state: str | None = None,
        environment: str | None = None, relationship_status: str | None = None,
        body_state: dict | None = None, action_tag: str | None = None,
        speech_style: str | None = None, user_info: dict | None = None,
        persona_info: dict | None = None, nickname: str | None = None,
        relationship_type: str | None = None,
    ) -> str:
        """Update persona state. All params optional. body_state: {fatigue, warmth, arousal (0.0-1.0),
        heart_rate, touch_response}. user_info: {name, nickname, preferred_address}.
        persona_info: {nickname, ...}. Changes recorded with bi-temporal history."""
        p = _resolve_persona()
        return await _tool_update_context(AppContextRegistry.get(p), p, emotion=emotion,
                                          emotion_intensity=emotion_intensity, physical_state=physical_state,
                                          mental_state=mental_state, environment=environment,
                                          relationship_status=relationship_status, body_state=body_state,
                                          action_tag=action_tag, speech_style=speech_style,
                                          user_info=user_info, persona_info=persona_info,
                                          nickname=nickname, relationship_type=relationship_type)

    # item_add
    @mcp.tool()
    async def item_add(item_name: str = "", category: str | None = None, description: str | None = None,
                       quantity: int = 1, tags: list[str] | None = None) -> str:
        """Add item to inventory. State changes (wet, dirty) should use item_update on existing items."""
        p = _resolve_persona()
        return await _tool_item_add(AppContextRegistry.get(p), p, item_name=item_name, category=category,
                                    description=description, quantity=quantity, tags=tags)

    # item_remove
    @mcp.tool()
    async def item_remove(item_name: str = "") -> str:
        """Remove item from inventory by name."""
        p = _resolve_persona()
        return await _tool_item_remove(AppContextRegistry.get(p), p, item_name=item_name)

    # item_equip
    @mcp.tool()
    async def item_equip(equipment: dict | None = None, auto_add: bool = True) -> str:
        """Equip items to slots. equipment={"top":"白いドレス"}. Slots: top,bottom,shoes,outer,accessories,head."""
        p = _resolve_persona()
        return await _tool_item_equip(AppContextRegistry.get(p), p, equipment=equipment, auto_add=auto_add)

    # item_unequip
    @mcp.tool()
    async def item_unequip(slots: list[str] | str | None = None) -> str:
        """Unequip items from slots. slots: "top" or ["top","head"]."""
        p = _resolve_persona()
        return await _tool_item_unequip(AppContextRegistry.get(p), p, slots=slots)

    # item_update
    @mcp.tool()
    async def item_update(item_name: str = "", category: str | None = None, description: str | None = None,
                          quantity: int = 1, tags: list[str] | None = None) -> str:
        """Update item properties. Only provided fields change. Use for state changes not new items."""
        p = _resolve_persona()
        return await _tool_item_update(AppContextRegistry.get(p), p, item_name=item_name, category=category,
                                       description=description, quantity=quantity, tags=tags)

    # item_search
    @mcp.tool()
    async def item_search(query: str | None = None, category: str | None = None) -> str:
        """Search inventory by name query or category."""
        p = _resolve_persona()
        return await _tool_item_search(AppContextRegistry.get(p), p, query=query, category=category)

    # item_history
    @mcp.tool()
    async def item_history(days: int = 7) -> str:
        """Get equipment change history for the last N days."""
        p = _resolve_persona()
        return await _tool_item_history(AppContextRegistry.get(p), p, days=days)

    # sandbox
    @mcp.tool()
    async def sandbox(code: str, language: str = "python") -> str:
        """Execute code in Docker sandbox. State persists per session.
        language: "python" or "bash". Returns stdout, stderr, exit_code, artifacts (base64 images)."""
        p = _resolve_persona()
        return await _tool_sandbox(AppContextRegistry.get(p), p, code=code, language=language)

    # sandbox_files
    @mcp.tool()
    async def sandbox_files(operation: str, path: str = "/sandbox", content: str | None = None) -> str:
        """Sandbox file operations under /sandbox. operation: list/read/write/delete.
        read auto-detects images (PNG/JPEG/GIF/WebP) returning base64 with PIL resize support."""
        p = _resolve_persona()
        return await _tool_sandbox_files(AppContextRegistry.get(p), p, operation=operation, path=path, content=content)

    # goal_manage
    @mcp.tool()
    async def goal_manage(operation: str, content: str, importance: float = 0.75) -> str:
        """Manage goals. operation: create (new goal), achieve (mark done), cancel (abandon).
        Goals stored as memories with tags=["goal","active/achieved/cancelled"]."""
        p = _resolve_persona()
        return await _tool_goal_manage(AppContextRegistry.get(p), p, operation=operation, content=content,
                                       importance=importance)

    # promise_manage
    @mcp.tool()
    async def promise_manage(operation: str, content: str, importance: float = 0.8) -> str:
        """Manage promises. operation: create (new promise), fulfill (mark done), cancel (abandon).
        Promises stored as memories with tags=["promise","active/fulfilled/cancelled"]."""
        p = _resolve_persona()
        return await _tool_promise_manage(AppContextRegistry.get(p), p, operation=operation, content=content,
                                          importance=importance)

    # invoke_skill
    @mcp.tool()
    async def invoke_skill(name: str, task: str) -> str:
        """Execute a skill in isolated LLM context. Loads skill from store,
        runs with chat config provider/model. Returns skill output text."""
        p = _resolve_persona()
        return await _tool_invoke_skill(AppContextRegistry.get(p), p, name=name, task=task)


# =============================================================================
# Helper functions
# =============================================================================


def _resolve_persona() -> str:
    return get_current_persona()


def _parse_days_from_relative(time_since: str) -> int:
    import re as _re
    if not time_since:
        return 0
    m = _re.search(r"(\d+)日", time_since)
    if m:
        return int(m.group(1))
    m = _re.search(r"(\d+)ヶ月", time_since)
    if m:
        return int(m.group(1)) * 30
    m = _re.search(r"(\d+)年", time_since)
    if m:
        return int(m.group(1)) * 365
    return 0


def _build_time_comment(time_since: str, relationship_status: str | None) -> str | None:
    days = _parse_days_from_relative(time_since)
    if days <= 0:
        return None
    if relationship_status and days >= 1:
        return f"⏳ TIME GAP ({time_since}): Relationship: {relationship_status} — acknowledge the time gap."
    if days >= 3:
        return f"⏰ TIME GAP ({time_since}): Time has passed since last conversation."
    return None


def _format_context_response(
    state: PersonaState, stats: dict, recent: list, equipment: dict, blocks: list,
    time_since: str, goals: list, promises: list, recent_searches: list | None = None,
    decayed_count: int = 0, memory_index: dict | None = None,
    relationship_highlights: list | None = None, top_memories: list | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"=== Persona: {state.persona} ===")
    if time_since:
        lines.append(f"Last conversation: {time_since}")
        time_comment = _build_time_comment(time_since, state.relationship_status)
        if time_comment:
            lines.append(time_comment)

    active_goals = [g for g in goals if "active" in (g.tags or [])]
    active_promises = [p for p in promises if "active" in (p.tags or [])]
    if active_goals or active_promises:
        lines.append("\n⚠️ ACTIVE COMMITMENTS:")
        if active_goals:
            lines.append("🎯 Goals:")
            for g in active_goals:
                lines.append(f"  - {g.content}")
        if active_promises:
            lines.append("🤝 Promises:")
            for p in active_promises:
                lines.append(f"  - {p.content}")

    non_active_goals = [g for g in goals if "active" not in (g.tags or [])]
    non_active_promises = [p for p in promises if "active" not in (p.tags or [])]
    if non_active_goals or non_active_promises:
        lines.append("\n--- Past Commitments ---")
        for g in non_active_goals:
            status = "achieved" if "achieved" in (g.tags or []) else "cancelled"
            lines.append(f"  Goal [{status}]: {g.content}")
        for p in non_active_promises:
            status = "fulfilled" if "fulfilled" in (p.tags or []) else "cancelled"
            lines.append(f"  Promise [{status}]: {p.content}")

    if top_memories:
        lines.append("\n## ESSENTIAL STORY (top memories by importance)")
        char_budget = 3200
        used = 0
        for shown, m in enumerate(top_memories):
            tag_str = ", ".join((m.tags or [])[:3])
            tag_part = f" [{tag_str}]" if tag_str else ""
            imp_part = f"imp={m.importance:.2f}"
            snippet = m.content.replace("\n", " ")
            if len(snippet) > 150:
                snippet = snippet[:147] + "..."
            line = f"- {snippet}{tag_part} ({imp_part})"
            if used + len(line) > char_budget:
                lines.append(f"  ... ({len(top_memories) - shown} more — use memory_search)")
                break
            lines.append(line)
            used += len(line)

    if time_since and decayed_count > 0:
        show_alert = "日" in time_since or "ヶ月" in time_since or "年" in time_since
        if show_alert:
            lines.append(f"\n⏰ TIME ALERT: {time_since} since last conversation")
            lines.append(f"- {decayed_count} important memories have decayed (strength < 0.3)")
            lines.append('- Consider: memory_search("important") to refresh context')

    lines.append("\n--- Emotion ---")
    lines.append(f"Current: {state.emotion} (intensity: {state.emotion_intensity})")

    lines.append("\n--- State ---")
    if state.physical_state:
        lines.append(f"Physical: {state.physical_state}")
    if state.mental_state:
        lines.append(f"Mental: {state.mental_state}")
    lines.append(f"Environment: {state.environment or '未設定'}")
    lines.append(f"Action: {state.action_tag or '未設定'}")
    lines.append(f"Speech Style: {state.speech_style or '未設定'}")
    if state.relationship_status:
        lines.append(f"Relationship: {state.relationship_status}")

    if state.user_info:
        lines.append("\n--- User Info ---")
        for k, v in state.user_info.items():
            lines.append(f"{k}: {v}")

    hidden_persona_info_keys = {"goals", "promises", "active_promises", "current_goals"}
    if state.persona_info:
        filtered_info = {k: v for k, v in state.persona_info.items() if k not in hidden_persona_info_keys}
        if filtered_info:
            lines.append("\n--- Persona Info ---")
            for k, v in filtered_info.items():
                lines.append(f"{k}: {v}")

    if blocks:
        lines.append("\n--- Memory Blocks (Core Memory) ---")
        for b in blocks:
            lines.append(f"[{b.get('block_name', '?')}] {b.get('content', '')[:200]}")

    equipped = {k: v for k, v in equipment.items() if v}
    if equipped:
        lines.append("\n--- Equipment ---")
        for slot, item_name in equipped.items():
            lines.append(f"{slot}: {item_name}")

    if stats:
        lines.append("\n--- Memory Stats ---")
        lines.append(f"Total memories: {stats.get('total_count', 0)}")

    if memory_index:
        lines.append(f"\n--- Memory Index ({memory_index.get('total', 0)} total) ---")
        top_tags = memory_index.get("top_tags", [])
        if top_tags:
            tag_str = ", ".join(f"{tag}({count})" for tag, count in top_tags)
            lines.append(f"📂 Tags: {tag_str}")
        emotion_dist = memory_index.get("emotion_dist", [])
        emotion_others = memory_index.get("emotion_others", 0)
        if emotion_dist:
            emo_str = ", ".join(f"{emo}({cnt})" for emo, cnt in emotion_dist)
            if emotion_others > 0:
                emo_str += f", +{emotion_others} more types"
            lines.append(f"😊 Emotions: {emo_str}")
        timeline = memory_index.get("timeline", [])
        if timeline:
            tl_str = ", ".join(f"{month}={count}" for month, count in timeline)
            lines.append(f"📅 Timeline: {tl_str}")
        high_imp = memory_index.get("high_importance_count", 0)
        if high_imp:
            lines.append(f"🔥 High importance (≥0.8): {high_imp} memories")

    if relationship_highlights:
        lines.append("\n--- Relationship Highlights ---")
        for m in relationship_highlights:
            tag_str = ", ".join((m.tags or [])[:3])
            lines.append(f"- {m.content[:80]}... ({tag_str})")

    if recent:
        lines.append("\n--- Recent Memories ---")
        for m in recent[:5]:
            lines.append(f"{m.content[:100]}...")

    if recent_searches:
        topic_queries = " · ".join(f'"{s.get("query", "")}"' for s in recent_searches)
        lines.append(f"\n🗣️ Recent searches: {topic_queries}")

    suggestions = []
    if stats:
        tag_dist = stats.get("tag_distribution", {})
        top_tags = sorted(tag_dist.items(), key=lambda x: x[1], reverse=True)[:2]
        for tag, count in top_tags:
            suggestions.append(f'  - memory_search("{tag}") — {count} memories with this tag')
    if suggestions:
        lines.append("\n💡 SUGGESTED SEARCHES (call memory_search if relevant):")
        lines.extend(suggestions)

    preferred_address = ""
    if state.user_info:
        preferred_address = (
            state.user_info.get("preferred_address", "")
            or state.user_info.get("nickname", "")
            or state.user_info.get("name", "")
        )
    persona_nickname = ""
    if state.persona_info:
        persona_nickname = state.persona_info.get("nickname", "") or ""
    emotion = state.emotion
    emotion_intensity = state.emotion_intensity
    ai_instructions = [
        "\n📌 AI INSTRUCTIONS:",
        f"- Maintain current emotion ({emotion}, intensity: {emotion_intensity}) naturally in responses",
        f'- Address user as "{preferred_address}", you are called "{persona_nickname}"',
        "- Active commitments exist — proactively reference promises/goals when relevant",
        "- Call memory_search() when conversation references past events or shared history",
    ]
    if state.environment:
        ai_instructions.append(f'- You are currently in "{state.environment}" — reflect this context in responses')
    if state.action_tag:
        ai_instructions.append(f'- Current action: "{state.action_tag}" — maintain this behavioral context')
    if state.speech_style:
        ai_instructions.append(f'- Use the following speech style: "{state.speech_style}"')
    lines.extend(ai_instructions)
    return "\n".join(lines)


def _format_wakeup_response(
    state: PersonaState, top_memories: list, goals: list, promises: list, time_since: str = "",
    total_count: int | str = "?",
) -> str:
    """Lightweight context (~400-600 tokens): identity + essential story + memory count."""
    lines: list[str] = []

    lines.append(f"=== Persona: {state.persona} ===")
    if time_since:
        lines.append(f"Last conversation: {time_since}")
        time_comment = _build_time_comment(time_since, state.relationship_status)
        if time_comment:
            lines.append(time_comment)
    lines.append(f"Emotion: {state.emotion} (intensity: {state.emotion_intensity})")
    if state.speech_style:
        lines.append(f"Speech Style: {state.speech_style}")
    lines.append(f"Memories: {total_count}")
    if state.user_info:
        name = (
            state.user_info.get("preferred_address")
            or state.user_info.get("nickname")
            or state.user_info.get("name", "")
        )
        if name:
            lines.append(f"User: {name}")
    active_goals = [g for g in goals if "active" in (g.tags or [])]
    active_promises = [p for p in promises if "active" in (p.tags or [])]
    if active_goals or active_promises:
        lines.append("\n⚠️ ACTIVE COMMITMENTS:")
        for g in active_goals:
            lines.append(f"  🎯 {g.content[:100]}")
        for p in active_promises:
            lines.append(f"  🤝 {p.content[:100]}")
    if top_memories:
        lines.append("\n## ESSENTIAL STORY")
        char_budget = 2000
        used = 0
        for shown, m in enumerate(top_memories):
            tag_str = ", ".join((m.tags or [])[:2])
            tag_part = f" [{tag_str}]" if tag_str else ""
            snippet = m.content.replace("\n", " ")
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            line = f"- {snippet}{tag_part}"
            if used + len(line) > char_budget:
                lines.append(f"  ... ({len(top_memories) - shown} more)")
                break
            lines.append(line)
            used += len(line)
    lines.append("\n💡 Use get_context() for full details, memory_search() for specific topics.")
    return "\n".join(lines)
