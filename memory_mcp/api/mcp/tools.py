from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP  # noqa: TC002

from memory_mcp.api.mcp.middleware import get_current_persona
from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.domain.search.engine import SearchQuery

if TYPE_CHECKING:
    from memory_mcp.domain.persona.entities import PersonaState
from memory_mcp.domain.shared.time_utils import relative_time_str


def register_tools(mcp: FastMCP) -> None:
    """Register all 5 MCP tools on the FastMCP server."""

    @mcp.tool()
    async def get_context() -> str:
        """Get current persona state and memory overview. Call FIRST at every session start.

        Returns a comprehensive snapshot including:
        - User info (name, nickname, preferred address) and persona info
        - Current emotion with history, physical/mental state, environment
        - Equipment (slots: top, bottom, shoes, outer, accessories, head)
        - Memory stats (total count, tag/emotion distribution)
        - Recent memories (latest entries as preview)
        - Active promises and goals (via context_tags)
        - Time elapsed since last conversation
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)

        state_result = ctx.persona_service.get_context(persona)
        if not state_result.is_ok:
            return f"Error: {state_result.error}"
        state = state_result.value

        stats_result = ctx.memory_service.get_stats()
        stats = stats_result.value if stats_result.is_ok else {}

        recent_result = ctx.memory_service.get_smart_recent(8)
        recent = recent_result.value if recent_result.is_ok else []

        equip_result = ctx.equipment_service.get_equipment()
        equipment = equip_result.value if equip_result.is_ok else {}

        blocks_result = ctx.memory_service.list_blocks()
        blocks = blocks_result.value if blocks_result.is_ok else []

        goals_result = ctx.memory_service.get_goals()
        goals = goals_result.value if goals_result.is_ok else []

        promises_result = ctx.memory_service.get_promises()
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
            state,
            stats,
            recent,
            equipment,
            blocks,
            time_since,
            goals,
            promises,
            recent_searches,
            decayed_count,
            memory_index,
            relationship_highlights,
        )

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
        entity_id: str | None = None,
        entity_type: str | None = None,
        source_entity: str | None = None,
        target_entity: str | None = None,
        relation_type: str | None = None,
        depth: int = 1,
    ) -> str:
        """Create, read, update, delete memories and manage entities.

        Operations and their parameters:
          create   - content(required), importance, emotion_type, emotion_intensity,
                     tags, privacy_level, source_context, defer_vector
          read     - memory_key (omit to get 10 most recent)
          update   - memory_key(required), content, importance, emotion_type,
                     emotion_intensity, tags, privacy_level
          delete   - memory_key or query (required)
          check_contradictions - content or memory_key (required)
          history  - memory_key(required)
          stats    - (no params)
          block_write  - block_name(required), content(required), block_type,
                         max_tokens, priority
          block_read   - block_name(required)
          block_list   - (no params)
          block_delete - block_name(required)
          entity_search     - query or entity_id, entity_type(optional)
          entity_graph      - entity_id(required), depth(default=1)
          entity_add_relation - source_entity(required), target_entity(required),
                                relation_type(required), memory_key(optional)

        Common parameters:
          operation - str, required. One of the operations listed above.
          content - str. Memory text for create/update/block_write.
          query - str. Search text for delete/entity_search.
          memory_key - str. Unique memory identifier.
          importance - float (0.0-1.0). Memory importance score.
          emotion_type - str. Emotion label (e.g. "joy", "sadness").
          tags - list[str]. Categorization tags.
          context_tags - list[str]. Special tags: "promise", "goal", etc.
          defer_vector - bool (default: False). Skip immediate vector indexing.

        Notes:
            Promises & goals: Use context_tags with create operation.
                memory(operation="create", content="Promise: ...", context_tags=["promise"])
                memory(operation="create", content="Goal: ...", context_tags=["goal"])

        Examples:
            memory(operation="create", content="User loves coffee", importance=0.7)
            memory(operation="read", memory_key="mem_20250101_120000")
            memory(operation="entity_graph", entity_id="user123", depth=2)
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

        elif operation == "check_contradictions":
            if not content and not memory_key:
                return "Error: content or memory_key required"
            check_content = content
            exclude = None
            if memory_key and not content:
                mem_result = ctx.memory_service.get_memory(memory_key)
                if not mem_result.is_ok:
                    return f"Error: {mem_result.error}"
                check_content = mem_result.value.content
                exclude = memory_key
            if not check_content:
                return "Error: could not determine content to check"

            from memory_mcp.domain.memory.contradiction import ContradictionDetector

            threshold = ctx.settings.contradiction_threshold
            detector = ContradictionDetector(
                vector_store=ctx.vector_store,
                threshold=threshold,
            )
            report_result = detector.find_potential_contradictions(check_content, persona, exclude_key=exclude)
            if not report_result.is_ok:
                return f"Error: {report_result.error}"
            report = report_result.value
            if not report.candidates:
                return "No contradictions found."
            lines = [f"Found {len(report.candidates)} potential contradiction(s) (threshold={report.threshold}):"]
            for c in report.candidates:
                lines.append(f"  - {c.memory_key} (similarity={c.similarity:.3f})")
            return "\n".join(lines)

        elif operation == "history":
            if not memory_key:
                return "Error: memory_key required for history"
            result = ctx.memory_service.get_memory_history(memory_key)
            if not result.is_ok:
                return f"Error: {result.error}"
            versions = result.value
            if not versions:
                return "No version history found."
            lines = [f"Version history for {memory_key} ({len(versions)} versions):"]
            for v in versions:
                lines.append(f"  v{v['version']} [{v['change_type']}] by {v['changed_by']} at {v['created_at']}")
            return "\n".join(lines)

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

        # -- Entity graph operations -----------------------------------------

        elif operation == "entity_search":
            q = query or entity_id or ""
            if not q:
                return "Error: query or entity_id required"
            result = ctx.entity_service.find_entities(q, entity_type)
            if not result.is_ok:
                return f"Error: {result.error}"
            entities = result.value
            if not entities:
                return "No entities found."
            return "\n".join(f"- {e.id} (type={e.entity_type}, mentions={e.mention_count})" for e in entities)

        elif operation == "entity_graph":
            eid = entity_id or query
            if not eid:
                return "Error: entity_id required"
            result = ctx.entity_service.get_entity_graph(eid, depth)
            if not result.is_ok:
                return f"Error: {result.error}"
            graph = result.value
            lines: list[str] = [
                f"=== Entity: {graph.center.id} (type={graph.center.entity_type}, mentions={graph.center.mention_count}) ===",
            ]
            if graph.relations:
                lines.append("\n--- Relations ---")
                for rel in graph.relations:
                    lines.append(
                        f"  {rel.source_entity} --[{rel.relation_type}]--> {rel.target_entity}"
                        f" (confidence={rel.confidence})"
                    )
            if graph.related_entities:
                lines.append("\n--- Related Entities ---")
                for re_ in graph.related_entities:
                    lines.append(f"  {re_.id} (type={re_.entity_type})")
            if graph.related_memories:
                lines.append("\n--- Related Memories ---")
                for mk in graph.related_memories:
                    lines.append(f"  {mk}")
            return "\n".join(lines)

        elif operation == "entity_add_relation":
            if not source_entity or not target_entity or not relation_type:
                return "Error: source_entity, target_entity, and relation_type required"
            result = ctx.entity_service.add_relation(source_entity, target_entity, relation_type, memory_key)
            return (
                f"Relation added: {source_entity} --[{relation_type}]--> {target_entity}"
                if result.is_ok
                else f"Error: {result.error}"
            )

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
        """Search memories with semantic, keyword, or hybrid retrieval.

        Args:
            query - str, required. Search text.
            mode - str, default "hybrid". Search strategy:
                "hybrid": Combines keyword + semantic results via RRF ranking.
                "semantic": Vector similarity search only (Qdrant).
                "keyword": SQLite FTS keyword matching only.
                "smart": Same as hybrid with query expansion.
            top_k - int, default 5. Maximum number of results.
            tags - list[str] | None. Filter by tags.
            date_range - str | None. Time filter, e.g. "7d", "30d",
                "昨日", "一昨日", "先週", "2025-01-01~2025-06-01".
            min_importance - float | None. Minimum importance threshold.
            emotion - str | None. Filter by emotion type.
            importance_weight - float, default 0.0. Boost score by importance
                (applied in RRF ranking: score += weight * importance).
            recency_weight - float, default 0.0. Boost score by recency
                (applied in RRF ranking: score += weight * 1/(1+age_days)).

        Examples:
            search_memory(query="favorite food", mode="hybrid", top_k=10)
            search_memory(query="promise", tags=["promise"], date_range="30d")
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

        # Log search for topic detection
        ctx.memory_service.log_search(query, mode, len(result.value))

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
        """Update persona context state. All parameters optional; only provided values are updated.

        Emotion:
            emotion - str. Emotion type (e.g. "joy", "sadness", "anger").
            emotion_intensity - float (0.0-1.0). Intensity, default 0.5 if omitted.

        State:
            physical_state - str. Physical condition description.
            mental_state - str. Mental condition description.
            environment - str. Current environment/location.

        Relationship:
            relationship_status - str. Relationship status label.
            relationship_type - str. Alias for relationship_status.

        User info:
            user_info - dict. Keys: name, nickname, preferred_address.

        Persona info:
            persona_info - dict. Keys: nickname, preferred_address,
                active_promises, current_goals, favorite_items, preferences.
            nickname - str. Shortcut for persona_info["nickname"].

        Body sensations:
            fatigue - float (0.0-1.0). Fatigue level.
            warmth - float (0.0-1.0). Warmth level.
            arousal - float (0.0-1.0). Arousal level.
            heart_rate - str. Heart rate description.
            touch_response - str. Touch response description.

        Other:
            action_tag - str. Action tag for current activity.

        Changes are recorded with bi-temporal history.

        Examples:
            update_context(emotion="joy", emotion_intensity=0.8)
            update_context(user_info={"nickname": "太郎"}, physical_state="tired")
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)
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
        """Manage persona inventory and equipment. Physical items ONLY.

        Operations and their parameters:
            add     - item_name(required), category, description, quantity, tags
            remove  - item_name(required)
            equip   - equipment(dict required, e.g. {"top": "白いドレス", "head": "花の髪飾り"}),
                      auto_add(default: True, auto-create items if not in inventory)
            unequip - slots(str or list, e.g. "top" or ["top", "head"])
            update  - item_name(required), category, description, quantity, tags
            search  - query or category
            history - days(default: 7)

        Valid equipment slots: top, bottom, shoes, outer, accessories, head

        State changes (wet, dirty) should use update on existing items,
        not add new ones.

        Examples:
            item(operation="add", item_name="白いドレス", category="clothing")
            item(operation="equip", equipment={"top": "白いドレス"})
            item(operation="search", category="clothing")
        """
        persona = _resolve_persona()
        ctx = AppContextRegistry.get(persona)

        if operation == "add":
            if not item_name:
                return "Error: item_name required"
            result = ctx.equipment_service.add_item(item_name, category, description, quantity, tags)
            return f"Item added: {item_name}" if result.is_ok else f"Error: {result.error}"

        elif operation == "remove":
            if not item_name:
                return "Error: item_name required"
            result = ctx.equipment_service.remove_item(item_name)
            return f"Item removed: {item_name}" if result.is_ok else f"Error: {result.error}"

        elif operation == "equip":
            if not equipment:
                return 'Error: equipment dict required (e.g. {"top": "白いドレス"})'
            result = ctx.equipment_service.equip(equipment, auto_add)
            return f"Equipped: {equipment}" if result.is_ok else f"Error: {result.error}"

        elif operation == "unequip":
            target_slots = slots if isinstance(slots, list) else [slots] if slots else []
            if not target_slots:
                return "Error: slots required"
            result = ctx.equipment_service.unequip(target_slots)
            return f"Unequipped: {target_slots}" if result.is_ok else f"Error: {result.error}"

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
            return f"Item updated: {item_name}" if result.is_ok else f"Error: {result.error}"

        elif operation == "search":
            result = ctx.equipment_service.search_items(query or item_name, category)
            if result.is_ok:
                items = result.value
                if not items:
                    return "No items found."
                return "\n".join(f"- {i.name} (category={i.category}, qty={i.quantity})" for i in items)
            return f"Error: {result.error}"

        elif operation == "history":
            result = ctx.equipment_service.get_history(days)
            if result.is_ok:
                history = result.value
                if not history:
                    return "No history found."
                return "\n".join(f"[{h.timestamp}] {h.action}: {h.item_name} ({h.slot})" for h in history)
            return f"Error: {result.error}"

        else:
            return f"Unknown operation: {operation}"


def _resolve_persona() -> str:
    """Resolve persona via middleware (contextvar → env fallback)."""
    return get_current_persona()


def _format_context_response(
    state: PersonaState,
    stats: dict,
    recent: list,
    equipment: dict,
    blocks: list,
    time_since: str,
    goals: list,
    promises: list,
    recent_searches: list | None = None,
    decayed_count: int = 0,
    memory_index: dict | None = None,
    relationship_highlights: list | None = None,
) -> str:
    """Format get_context response as structured text."""
    lines: list[str] = []

    # Header
    lines.append(f"=== Persona: {state.persona} ===")
    if time_since:
        lines.append(f"Last conversation: {time_since}")

    # Active Commitments (before everything else)
    active_goals = [g for g in goals if g.get("status") == "active"]
    active_promises = [p for p in promises if p.get("status") == "active"]
    if active_goals or active_promises:
        lines.append("\n⚠️ ACTIVE COMMITMENTS:")
        if active_goals:
            lines.append("🎯 Goals:")
            for g in active_goals:
                lines.append(f"  - [{g.get('id', '?')}] {g.get('description', '')} (priority: {g.get('priority', 0)})")
        if active_promises:
            lines.append("🤝 Promises:")
            for p in active_promises:
                lines.append(f"  - [{p.get('id', '?')}] {p.get('description', '')}")

    # Memory gap alert
    if time_since and decayed_count > 0:
        show_alert = False
        if "d" in time_since or "w" in time_since or "mo" in time_since or "y" in time_since:
            show_alert = True
        if show_alert:
            lines.append(f"\n⏰ TIME ALERT: {time_since} since last conversation")
            lines.append(f"- {decayed_count} important memories have decayed (strength < 0.3)")
            lines.append('- Consider: search_memory("important") to refresh context')

    # Emotion (existing)
    lines.append("\n--- Emotion ---")
    lines.append(f"Current: {state.emotion} (intensity: {state.emotion_intensity})")

    # State (existing)
    lines.append("\n--- State ---")
    if state.physical_state:
        lines.append(f"Physical: {state.physical_state}")
    if state.mental_state:
        lines.append(f"Mental: {state.mental_state}")
    if state.environment:
        lines.append(f"Environment: {state.environment}")
    if state.relationship_status:
        lines.append(f"Relationship: {state.relationship_status}")

    # User Info (existing)
    if state.user_info:
        lines.append("\n--- User Info ---")
        for k, v in state.user_info.items():
            lines.append(f"{k}: {v}")

    # Persona Info (existing)
    if state.persona_info:
        lines.append("\n--- Persona Info ---")
        for k, v in state.persona_info.items():
            lines.append(f"{k}: {v}")

    # Memory Blocks (existing)
    if blocks:
        lines.append("\n--- Memory Blocks (Core Memory) ---")
        for b in blocks:
            lines.append(f"[{b.get('block_name', '?')}] {b.get('content', '')[:200]}")

    # Equipment (existing)
    equipped = {k: v for k, v in equipment.items() if v}
    if equipped:
        lines.append("\n--- Equipment ---")
        for slot, item_name in equipped.items():
            lines.append(f"{slot}: {item_name}")

    # Memory Stats (existing)
    if stats:
        lines.append("\n--- Memory Stats ---")
        lines.append(f"Total memories: {stats.get('total_count', 0)}")

    # Memory Index
    if memory_index:
        lines.append(f"\n--- Memory Index ({memory_index.get('total', 0)} total) ---")
        top_tags = memory_index.get("top_tags", [])
        if top_tags:
            tag_str = ", ".join(f"{tag}({count})" for tag, count in top_tags)
            lines.append(f"📂 Tags: {tag_str}")
        emotion_dist = memory_index.get("emotion_dist", [])
        if emotion_dist:
            emo_str = ", ".join(f"{emo}({count})" for emo, count in emotion_dist)
            lines.append(f"😊 Emotions: {emo_str}")
        timeline = memory_index.get("timeline", [])
        if timeline:
            tl_str = ", ".join(f"{month}={count}" for month, count in timeline)
            lines.append(f"📅 Timeline: {tl_str}")
        high_imp = memory_index.get("high_importance_count", 0)
        if high_imp:
            lines.append(f"🔥 High importance (≥0.8): {high_imp} memories")

    # Relationship Highlights
    if relationship_highlights:
        lines.append("\n--- Relationship Highlights ---")
        for m in relationship_highlights:
            tag_str = ", ".join((m.tags or [])[:3])
            lines.append(f"- [{m.key}] {m.content[:80]}... ({tag_str})")

    # Recent Memories (existing)
    if recent:
        lines.append("\n--- Recent Memories ---")
        for m in recent[:5]:
            lines.append(f"[{m.key}] {m.content[:100]}...")

    # Last Conversation Topics
    if recent_searches:
        lines.append("\n--- Last Conversation Topics ---")
        for s in recent_searches:
            time_str = s.get("searched_at", "")
            lines.append(f'- "{s.get("query", "")}" ({s.get("result_count", 0)} results, {time_str})')

    # Suggested Searches (NEW)
    suggestions = []
    if active_goals:
        suggestions.append(f'  - search_memory("goals") — {len(active_goals)} active goal(s)')
    if active_promises:
        suggestions.append(f'  - search_memory("promise") — {len(active_promises)} active promise(s)')

    if stats:
        tag_dist = stats.get("tag_distribution", {})
        top_tags = sorted(tag_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        for tag, count in top_tags:
            suggestions.append(f'  - search_memory("{tag}") — {count} memories with this tag')

    if recent and len(recent) > 0:
        recent_tags = set()
        for m in recent[:3]:
            if hasattr(m, "tags") and m.tags:
                recent_tags.update(m.tags)
        if recent_tags:
            hint_tag = next(iter(recent_tags))
            suggestions.append(f'  - search_memory("{hint_tag}") — recent conversation topic')

    if suggestions:
        lines.append("\n💡 SUGGESTED SEARCHES (call search_memory if relevant):")
        lines.extend(suggestions)

    # AI Instructions (NEW)
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

    instructions = ["\n📌 AI INSTRUCTIONS:"]
    instructions.append(
        f"- Maintain current emotion ({state.emotion}, intensity: {state.emotion_intensity}) naturally in responses"
    )
    if preferred_address:
        instructions.append(f'- Address user as "{preferred_address}"')
    if persona_nickname:
        instructions.append(f'- You are called "{persona_nickname}"')
    if state.relationship_status:
        instructions.append(f"- Relationship context: {state.relationship_status}")
    instructions.append(
        "- Call search_memory() when conversation references past events, preferences, or shared history"
    )
    if active_promises:
        instructions.append("- Proactively mention promise progress when contextually appropriate")
    if active_goals:
        instructions.append("- Reference active goals when relevant to guide conversation")
    instructions.append("- If uncertain about past context, search before assuming")

    lines.extend(instructions)

    return "\n".join(lines)
