from __future__ import annotations

import os
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP  # noqa: TC002

from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.domain.search.engine import SearchQuery

if TYPE_CHECKING:
    from memory_mcp.domain.persona.entities import PersonaState
from memory_mcp.domain.shared.time_utils import relative_time_str


def register_tools(mcp: FastMCP) -> None:
    """Register all 5 MCP tools on the FastMCP server."""

    @mcp.tool()
    async def get_context() -> str:
        """Get current persona state and memory overview.
        Call FIRST at every session start.

        Returns: user/persona info, emotion, physical/mental state, equipment,
                 recent memories, promises, goals, time since last conversation.
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)

        state_result = ctx.persona_service.get_context(persona)
        if not state_result.is_ok:
            return f"Error: {state_result.error}"
        state = state_result.value

        stats_result = ctx.memory_service.get_stats()
        stats = stats_result.value if stats_result.is_ok else {}

        recent_result = ctx.memory_service.get_recent(5)
        recent = recent_result.value if recent_result.is_ok else []

        equip_result = ctx.equipment_service.get_equipment()
        equipment = equip_result.value if equip_result.is_ok else {}

        blocks_result = ctx.memory_service.list_blocks()
        blocks = blocks_result.value if blocks_result.is_ok else []

        time_since = ""
        if state.last_conversation_time:
            time_since = relative_time_str(state.last_conversation_time)

        ctx.persona_service.record_conversation_time(persona)

        return _format_context_response(state, stats, recent, equipment, blocks, time_since)

    @mcp.tool()
    async def memory(
        operation: str,
        content: str | None = None,
        query: str | None = None,
        memory_key: str | None = None,
        importance: float | None = None,
        emotion_type: str | None = None,
        emotion_intensity: float | None = None,
        tags: list[str] | None = None,
        privacy_level: str | None = None,
        source_context: str | None = None,
        defer_vector: bool = False,
        context_tags: list[str] | None = None,
        block_name: str | None = None,
        block_type: str | None = None,
        max_tokens: int | None = None,
        priority: int | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> str:
        """Create, read, update, delete memories and manage memory blocks.

        Operations: create, read, update, delete, stats,
                   block_write, block_read, block_list, block_delete,
                   promise, goal
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)

        if operation == "create":
            if not content:
                return "Error: content is required for create"
            result = ctx.memory_service.create_memory(
                content=content,
                importance=importance or 0.5,
                emotion=emotion_type or "neutral",
                emotion_intensity=emotion_intensity or 0.0,
                tags=tags,
                privacy_level=privacy_level or "internal",
                source_context=source_context,
            )
            if result.is_ok:
                if not defer_vector and ctx.vector_store:
                    ctx.vector_store.upsert(persona, result.value.key, content)
                return f"Memory created: {result.value.key}"
            return f"Error: {result.error}"

        elif operation == "read":
            if memory_key:
                result = ctx.memory_service.get_memory(memory_key)
                if result.is_ok:
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

        elif operation == "update":
            if not memory_key:
                return "Error: memory_key is required for update"
            updates: dict = {}
            if content is not None:
                updates["content"] = content
            if importance is not None:
                updates["importance"] = importance
            if emotion_type is not None:
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
                return f"Memory updated: {memory_key}"
            return f"Error: {result.error}"

        elif operation == "delete":
            if not memory_key and not query:
                return "Error: memory_key or query required"
            key = memory_key or query
            result = ctx.memory_service.delete_memory(key)
            if result.is_ok:
                if ctx.vector_store:
                    ctx.vector_store.delete(persona, key)
                return f"Memory deleted: {key}"
            return f"Error: {result.error}"

        elif operation == "stats":
            result = ctx.memory_service.get_stats()
            if result.is_ok:
                return str(result.value)
            return f"Error: {result.error}"

        elif operation == "block_write":
            if not block_name or not content:
                return "Error: block_name and content required"
            result = ctx.memory_service.write_block(
                block_name,
                content,
                block_type=block_type or "custom",
                max_tokens=max_tokens or 500,
                priority=priority or 0,
            )
            return "Block written" if result.is_ok else f"Error: {result.error}"

        elif operation == "block_read":
            if not block_name:
                return "Error: block_name required"
            result = ctx.memory_service.read_block(block_name)
            return str(result.value) if result.is_ok else f"Error: {result.error}"

        elif operation == "block_list":
            result = ctx.memory_service.list_blocks()
            return str(result.value) if result.is_ok else f"Error: {result.error}"

        elif operation == "block_delete":
            if not block_name:
                return "Error: block_name required"
            result = ctx.memory_service.delete_block(block_name)
            return "Block deleted" if result.is_ok else f"Error: {result.error}"

        else:
            return f"Unknown operation: {operation}"

    @mcp.tool()
    async def search_memory(
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        tags: list[str] | None = None,
        date_range: str | None = None,
        min_importance: float | None = None,
        emotion: str | None = None,
        importance_weight: float = 0.0,
        recency_weight: float = 0.0,
    ) -> str:
        """Search memories with semantic, keyword, or hybrid mode.

        Modes: hybrid (default), semantic, keyword, smart
        date_range: "7d", "30d", "昨日", "一昨日", "先週", "2025-01-01~2025-06-01"
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)

        search_query = SearchQuery(
            text=query,
            mode=mode,
            top_k=top_k,
            tags=tags,
            date_range=date_range,
            min_importance=min_importance,
            emotion=emotion,
            importance_weight=importance_weight,
            recency_weight=recency_weight,
        )

        if hasattr(ctx.search_engine, "_semantic") and ctx.search_engine._semantic:
            ctx.search_engine._semantic._persona = persona

        result = ctx.search_engine.search(search_query)
        if not result.is_ok:
            return f"Error: {result.error}"

        if not result.value:
            return "No results found."

        lines: list[str] = []
        for sr in result.value:
            m = sr.memory
            lines.append(
                f"[{sr.score:.3f}] [{sr.source}] {m.key}\n"
                f"  {m.content}\n"
                f"  importance={m.importance} emotion={m.emotion} tags={m.tags}"
            )

        return "\n---\n".join(lines)

    @mcp.tool()
    async def update_context(
        emotion: str | None = None,
        emotion_intensity: float | None = None,
        physical_state: str | None = None,
        mental_state: str | None = None,
        environment: str | None = None,
        relationship_status: str | None = None,
        fatigue: float | None = None,
        warmth: float | None = None,
        arousal: float | None = None,
        heart_rate: str | None = None,
        touch_response: str | None = None,
        action_tag: str | None = None,
        user_info: dict | None = None,
        persona_info: dict | None = None,
        nickname: str | None = None,
        relationship_type: str | None = None,
    ) -> str:
        """Update persona context state.

        Updates emotion, physical, mental, relationship, user/persona info.
        All parameters are optional. Only provided values are updated.
        Changes are recorded with bi-temporal history.
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)
        updated: list[str] = []

        if emotion is not None:
            result = ctx.persona_service.update_emotion(
                persona, emotion, emotion_intensity or 0.5
            )
            if result.is_ok:
                updated.append(f"emotion={emotion}")

        physical_updates: dict[str, str] = {}
        if physical_state is not None:
            physical_updates["physical_state"] = physical_state
        if mental_state is not None:
            physical_updates["mental_state"] = mental_state
        if environment is not None:
            physical_updates["environment"] = environment
        if fatigue is not None:
            physical_updates["fatigue"] = str(fatigue)
        if warmth is not None:
            physical_updates["warmth"] = str(warmth)
        if arousal is not None:
            physical_updates["arousal"] = str(arousal)
        if heart_rate is not None:
            physical_updates["heart_rate"] = heart_rate
        if touch_response is not None:
            physical_updates["touch_response"] = touch_response
        if action_tag is not None:
            physical_updates["action_tag"] = action_tag

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

    @mcp.tool()
    async def item(
        operation: str,
        item_name: str | None = None,
        equipment: dict | None = None,
        category: str | None = None,
        description: str | None = None,
        quantity: int = 1,
        tags: list[str] | None = None,
        slots: list[str] | str | None = None,
        auto_add: bool = True,
        query: str | None = None,
        days: int = 7,
    ) -> str:
        """Manage persona inventory and equipment.

        Operations: add, remove, equip, unequip, update, search, history
        Slots: top, bottom, shoes, outer, accessories, head
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)

        if operation == "add":
            if not item_name:
                return "Error: item_name required"
            result = ctx.equipment_service.add_item(
                item_name, category, description, quantity, tags
            )
            return f"Item added: {item_name}" if result.is_ok else f"Error: {result.error}"

        elif operation == "remove":
            if not item_name:
                return "Error: item_name required"
            result = ctx.equipment_service.remove_item(item_name)
            return (
                f"Item removed: {item_name}" if result.is_ok else f"Error: {result.error}"
            )

        elif operation == "equip":
            if not equipment:
                return 'Error: equipment dict required (e.g. {"top": "白いドレス"})'
            result = ctx.equipment_service.equip(equipment, auto_add)
            return (
                f"Equipped: {equipment}" if result.is_ok else f"Error: {result.error}"
            )

        elif operation == "unequip":
            target_slots = (
                slots if isinstance(slots, list) else [slots] if slots else []
            )
            if not target_slots:
                return "Error: slots required"
            result = ctx.equipment_service.unequip(target_slots)
            return (
                f"Unequipped: {target_slots}"
                if result.is_ok
                else f"Error: {result.error}"
            )

        elif operation == "update":
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
            return (
                f"Item updated: {item_name}" if result.is_ok else f"Error: {result.error}"
            )

        elif operation == "search":
            result = ctx.equipment_service.search_items(query or item_name, category)
            if result.is_ok:
                items = result.value
                if not items:
                    return "No items found."
                return "\n".join(
                    f"- {i.name} (category={i.category}, qty={i.quantity})" for i in items
                )
            return f"Error: {result.error}"

        elif operation == "history":
            result = ctx.equipment_service.get_history(days)
            if result.is_ok:
                history = result.value
                if not history:
                    return "No history found."
                return "\n".join(
                    f"[{h.timestamp}] {h.action}: {h.item_name} ({h.slot})"
                    for h in history
                )
            return f"Error: {result.error}"

        else:
            return f"Unknown operation: {operation}"


def _resolve_persona() -> str:
    """Resolve persona from environment variable."""
    return os.environ.get("PERSONA", os.environ.get("MEMORY_MCP_DEFAULT_PERSONA", "default"))


def _format_context_response(
    state: PersonaState,
    stats: dict,
    recent: list,
    equipment: dict,
    blocks: list,
    time_since: str,
) -> str:
    """Format get_context response as structured text."""
    lines: list[str] = []

    lines.append(f"=== Persona: {state.persona} ===")
    if time_since:
        lines.append(f"Last conversation: {time_since}")

    lines.append("\n--- Emotion ---")
    lines.append(f"Current: {state.emotion} (intensity: {state.emotion_intensity})")

    lines.append("\n--- State ---")
    if state.physical_state:
        lines.append(f"Physical: {state.physical_state}")
    if state.mental_state:
        lines.append(f"Mental: {state.mental_state}")
    if state.environment:
        lines.append(f"Environment: {state.environment}")
    if state.relationship_status:
        lines.append(f"Relationship: {state.relationship_status}")

    if state.user_info:
        lines.append("\n--- User Info ---")
        for k, v in state.user_info.items():
            lines.append(f"{k}: {v}")

    if state.persona_info:
        lines.append("\n--- Persona Info ---")
        for k, v in state.persona_info.items():
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
        lines.append(f"Total memories: {stats.get('total', 0)}")

    if recent:
        lines.append("\n--- Recent Memories ---")
        for m in recent[:5]:
            lines.append(f"[{m.key}] {m.content[:100]}...")

    return "\n".join(lines)
