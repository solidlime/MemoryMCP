"""Auto-generated from tools.py split — _tools_memory.py."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from memory_mcp.domain.search.engine import SearchQuery
from memory_mcp.domain.value_objects import _VALID_EMOTIONS, normalize_importance

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext


async def _tool_memory_create(
    ctx: AppContext,
    persona: str,
    content: str = "",
    importance: float | None = None,
    tags: list[str] | None = None,
    privacy_level: str = "internal",
    source_context: str | None = None,
    defer_vector: bool = False,
) -> str:
    """Create a memory. Current persona state (emotion, body_state) is automatically
    snapshotted at creation time. Always call context_update/update_context *before*
    memory_create if your emotional/physical state has changed, so the snapshot
    captures your latest state."""
    if not content:
        return "Error: content is required"
    if importance is not None and not (0.0 <= importance <= 1.0):
        return "Error: importance must be between 0.0 and 1.0"
    importance = importance if importance is not None else 0.5

    # Auto-snapshot current persona state
    emotion_snap, intensity_snap, body_snap, snapped_at = ctx.persona_service.get_state_snapshot(persona)

    result = ctx.memory_service.create_memory(
        content=content,
        importance=importance,
        tags=tags,
        privacy_level=privacy_level or "internal",
        source_context=source_context,
        emotion=emotion_snap,
        emotion_intensity=intensity_snap,
        body_state=body_snap,
        state_snapped_at=snapped_at,
    )
    if result.is_ok:
        if not defer_vector and ctx.vector_store:
            ctx.vector_store.upsert(persona, result.value.key, content)
        await ctx.event_bus.publish(
            "memory.created",
            {
                "key": result.value.key,
                "persona": persona,
                "content_preview": content[:100],
                "tags": tags or [],
                "importance": importance,
            },
        )
        return f"Memory created: {result.value.key}"
    return f"Error: {result.error}"


async def _tool_memory_read(
    ctx: AppContext,
    persona: str,
    memory_key: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> str:
    """Read a memory by key, or list most recent if key omitted. Use limit/offset for pagination."""
    if memory_key:
        result = ctx.memory_service.get_memory(memory_key)
        if result.is_ok:
            try:
                ctx.memory_service.boost_recall(memory_key)
            except Exception as e:
                logger.warning(f"boost_recall failed: {e}")
            m = result.value
            emotion_line = f"Emotion: {m.emotion}"
            if m.emotion_intensity:
                emotion_line += f" (intensity: {m.emotion_intensity})"
            result_text = (
                f"Key: {m.key}\nContent: {m.content}\n"
                f"Importance: {m.importance}\n{emotion_line}\n"
                f"Tags: {m.tags}\nCreated: {m.created_at}"
            )
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "memory_read",
                    "params_summary": f"memory_key={memory_key}",
                    "result_summary": f"Read memory: {m.key}",
                    "success": True,
                },
            )
            return result_text
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "memory_read",
                "params_summary": f"memory_key={memory_key}",
                "result_summary": str(result.error),
                "success": False,
            },
        )
        return f"Error: {result.error}"
    else:
        result = ctx.memory_service.get_recent(limit=limit + offset)
        if result.is_ok:
            items = result.value[offset : offset + limit]
            result_text = "\n---\n".join(f"[{m.key}] {m.content}" for m in items)
            await ctx.event_bus.publish(
                "tool.called",
                {
                    "persona": persona,
                    "tool_name": "memory_read",
                    "params_summary": f"limit={limit}, offset={offset}",
                    "result_summary": f"Listed {len(items)} recent memories",
                    "success": True,
                },
            )
            return result_text
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "memory_read",
                "params_summary": f"limit={limit}, offset={offset}",
                "result_summary": str(result.error),
                "success": False,
            },
        )
        return f"Error: {result.error}"


async def _tool_memory_update(
    ctx: AppContext,
    persona: str,
    memory_key: str = "",
    content: str | None = None,
    importance: float | None = None,
    emotion: str | None = None,
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
        updates["importance"] = normalize_importance(importance)
    update_warning = ""
    if emotion is not None:
        if emotion not in _VALID_EMOTIONS:
            update_warning = f"[Warning: emotion '{emotion}' is not a valid emotion, defaulted to 'neutral']\n"
        updates["emotion"] = emotion
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
        await ctx.event_bus.publish(
            "memory.updated",
            {
                "key": memory_key,
                "persona": persona,
                "content_preview": (content or "...")[:100],
                "changes": [
                    k for k in ["content", "importance", "tags", "privacy_level"] if locals().get(k) is not None
                ],
            },
        )
        return f"{update_warning}Memory updated: {memory_key}"
    return f"Error: {result.error}"


async def _tool_memory_delete(
    ctx: AppContext, persona: str, memory_key: str | None = None, query: str | None = None
) -> str:
    """Delete a memory by key, or search and delete the top match by query."""
    if not memory_key and not query:
        return "Error: memory_key or query required"

    # If query provided without key, search first
    key = memory_key
    content_preview = "..."
    if not key and query:
        search_result = ctx.search_engine.search(SearchQuery(text=query, top_k=1))
        if search_result.is_ok and search_result.value:
            m = search_result.value[0].memory
            key = m.key
            content_preview = m.content[:100]
            snippet = f"\nContent: 「{m.content[:80]}{'...' if len(m.content) > 80 else ''}」"
        else:
            return f"No memory found for query: {query}"
    else:
        snippet = ""
        pre_fetch = ctx.memory_service.get_memory(key)
        if pre_fetch.is_ok:
            content_preview = pre_fetch.value.content[:100]
            snippet = (
                f"\nContent: 「{pre_fetch.value.content[:80]}{'...' if len(pre_fetch.value.content) > 80 else ''}」"
            )

    result = ctx.memory_service.delete_memory(key)
    if result.is_ok:
        if ctx.vector_store:
            ctx.vector_store.delete(persona, key)
        await ctx.event_bus.publish(
            "memory.deleted",
            {
                "key": key,
                "persona": persona,
                "content_preview": content_preview,
            },
        )
        return f"Memory deleted: {key}{snippet}"
    return f"Error: {result.error}"


async def _tool_memory_search(
    ctx: AppContext,
    persona: str,
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
        text=query,
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
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "memory_search",
                "params_summary": f"query={query[:50]}, top_k={top_k}",
                "result_summary": str(result.error),
                "success": False,
            },
        )
        return f"Error: {result.error}"
    if not result.value:
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "memory_search",
                "params_summary": f"query={query[:50]}, top_k={top_k}",
                "result_summary": "No results found",
                "success": True,
            },
        )
        return "No results found."
    ctx.memory_service.log_search(query, "hybrid", len(result.value))

    lines: list[str] = []
    for sr in result.value:
        m = sr.memory
        emotion_str = f"{m.emotion}={m.emotion_intensity:.2f}" if m.emotion_intensity else m.emotion
        lines.append(
            f"[{sr.score:.3f}] [{sr.source}] {m.key}\n"
            f"  {m.content}\n"
            f"  importance={m.importance} emotion={emotion_str} tags={m.tags}"
        )
    result_text = "\n---\n".join(lines)
    await ctx.event_bus.publish(
        "tool.called",
        {
            "persona": persona,
            "tool_name": "memory_search",
            "params_summary": f"query={query[:50]}, top_k={top_k}",
            "result_summary": f"Found {len(result.value)} results",
            "success": True,
        },
    )
    return result_text


async def _tool_memory_stats(ctx: AppContext, persona: str, top_n: int = 20) -> str:
    """Get memory statistics."""
    result = ctx.memory_service.get_stats(top_n=top_n)
    if result.is_ok:
        result_text = str(result.value)
        await ctx.event_bus.publish(
            "tool.called",
            {
                "persona": persona,
                "tool_name": "memory_stats",
                "params_summary": f"top_n={top_n}",
                "result_summary": f"Stats retrieved ({len(result_text)} chars)",
                "success": True,
            },
        )
        return result_text
    await ctx.event_bus.publish(
        "tool.called",
        {
            "persona": persona,
            "tool_name": "memory_stats",
            "params_summary": f"top_n={top_n}",
            "result_summary": str(result.error),
            "success": False,
        },
    )
    return f"Error: {result.error}"
