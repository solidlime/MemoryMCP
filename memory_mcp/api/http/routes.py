from __future__ import annotations

import asyncio
import contextlib
import io
import os
import shutil
import zipfile
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from starlette.requests import Request  # noqa: TC002
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse  # noqa: TC002

from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.config.settings import Settings


def _safe_get_context(persona: str):
    """Get AppContext for persona, returning None if init fails."""
    try:
        return AppContextRegistry.get(persona)
    except Exception:
        return None


def _memory_to_dict(m) -> dict:
    """Convert a Memory dataclass to a JSON-safe dict."""
    d = asdict(m)
    for k in ("created_at", "updated_at", "last_accessed", "last_decay", "last_recall"):
        if k in d and d[k] is not None:
            d[k] = d[k].isoformat()
    # Rename emotion → emotion_type: domain model uses 'emotion', API/JS uses 'emotion_type'
    if "emotion" in d:
        d["emotion_type"] = d.pop("emotion")
    return d


def _strength_to_dict(s) -> dict:
    """Convert a MemoryStrength dataclass to a JSON-safe dict."""
    d = asdict(s)
    for k in ("last_decay", "last_recall"):
        if k in d and d[k] is not None:
            d[k] = d[k].isoformat()
    return d


def _resolve_persona_from_request(request: Request, *, default: str | None = None) -> str:
    """Resolve persona from path params, HTTP headers, or environment.

    Priority: path parameter > Bearer token > X-Persona header > *default* > env var.
    """
    persona = request.path_params.get("persona")
    if persona:
        return persona

    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token:
            return token

    x_persona = request.headers.get("x-persona")
    if x_persona:
        stripped = x_persona.strip()
        if stripped:
            return stripped

    if default is not None:
        return default
    return os.environ.get("PERSONA", os.environ.get("MEMORY_MCP_DEFAULT_PERSONA", "default"))


def register_http_routes(mcp) -> None:  # noqa: C901, PLR0915
    """Register HTTP routes on the FastMCP server."""

    # ------------------------------------------------------------------
    # Core routes
    # ------------------------------------------------------------------

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        """Health check endpoint."""
        ctx = AppContextRegistry.get(_resolve_persona_from_request(request, default="default"))
        qdrant_ok = ctx.vector_store is not None
        return JSONResponse(
            {
                "status": "ok",
                "version": "2.0.0",
                "qdrant": "connected" if qdrant_ok else "unavailable",
            }
        )

    @mcp.custom_route("/api/personas", methods=["GET"])
    async def list_personas(request: Request) -> JSONResponse:
        """List available personas by scanning data directory."""
        settings = Settings()
        data_dir = settings.data_dir
        data_path = Path(data_dir)
        if data_path.exists():
            personas = sorted([d.name for d in data_path.iterdir() if d.is_dir() and (d / "memory.sqlite").exists()])
        else:
            personas = []
        return JSONResponse({"personas": personas})

    @mcp.custom_route("/api/stats/{persona}", methods=["GET"])
    async def persona_stats(request: Request) -> JSONResponse:
        """Get stats for a specific persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        stats = ctx.memory_service.get_stats()
        return JSONResponse(stats.value if stats.is_ok else {"error": str(stats.error)})

    # ------------------------------------------------------------------
    # Dashboard routes (8 endpoints)
    # ------------------------------------------------------------------

    @mcp.custom_route("/", methods=["GET"])
    async def dashboard_page(request: Request) -> HTMLResponse:
        """Serve the dashboard HTML page (no persona pre-selected)."""
        from memory_mcp.api.http.dashboard import render_dashboard

        return HTMLResponse(render_dashboard())

    @mcp.custom_route("/dashboard/{persona}", methods=["GET"])
    async def dashboard_page_persona(request: Request) -> HTMLResponse:
        """Serve the dashboard HTML page with a specific persona pre-selected."""
        from memory_mcp.api.http.dashboard import render_dashboard

        persona = _resolve_persona_from_request(request)
        return HTMLResponse(render_dashboard(persona))

    @mcp.custom_route("/api/dashboard/{persona}", methods=["GET"])
    async def dashboard_data(request: Request) -> JSONResponse:
        """Aggregated dashboard data for a persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            # Stats
            stats_result = ctx.memory_service.get_stats()
            stats = stats_result.value if stats_result.is_ok else {}

            # Persona context
            context_result = ctx.persona_service.get_context(persona)
            context = asdict(context_result.value) if context_result.is_ok else {}
            # Serialise datetimes in context
            if "last_conversation_time" in context and context["last_conversation_time"] is not None:
                context["last_conversation_time"] = context["last_conversation_time"].isoformat()

            # Recent memories
            recent_result = ctx.memory_service.get_recent(limit=5)
            recent = [_memory_to_dict(m) for m in recent_result.value] if recent_result.is_ok else []

            # Memory blocks
            blocks_result = ctx.memory_service.list_blocks()
            blocks = blocks_result.value if blocks_result.is_ok else []

            # Equipment
            equip_result = ctx.equipment_service.get_equipment()
            equipment = equip_result.value if equip_result.is_ok else {}

            # Inventory items
            items_result = ctx.equipment_service.search_items()
            items_raw = items_result.value if items_result.is_ok else []
            items = []
            for it in items_raw:
                d = asdict(it)
                for k in ("created_at", "updated_at"):
                    if k in d and d[k] is not None:
                        d[k] = d[k].isoformat()
                items.append(d)

            # Strengths summary
            strength_result = ctx.memory_repo.get_all_strengths()
            strengths_raw = strength_result.value if strength_result.is_ok else []
            strength_values = [s.strength for s in strengths_raw]
            strengths_summary = {
                "total": len(strength_values),
                "avg": round(sum(strength_values) / len(strength_values), 3) if strength_values else None,
                "min": round(min(strength_values), 3) if strength_values else None,
                "max": round(max(strength_values), 3) if strength_values else None,
            }

            # Goals & Promises
            goals_result = ctx.memory_repo.get_goals()
            goals = goals_result.value if goals_result.is_ok else []

            promises_result = ctx.memory_repo.get_promises()
            promises = promises_result.value if promises_result.is_ok else []

            # Inject linked_ratio: ratio of memories that are linked to entities
            try:
                total_count = stats.get("total_count", 0)
                if total_count > 0:
                    linked_row = ctx.entity_repo._db.execute(
                        "SELECT COUNT(DISTINCT memory_key) AS cnt FROM memory_entities WHERE memory_key != ''"
                    ).fetchone()
                    linked_count = linked_row["cnt"] if linked_row else 0
                    stats["linked_ratio"] = min(linked_count / total_count, 1.0)
            except Exception:
                pass

            return JSONResponse(
                {
                    "persona": persona,
                    "stats": stats,
                    "context": context,
                    "recent": recent,
                    "blocks": blocks,
                    "equipment": equipment,
                    "items": items,
                    "strengths": strengths_summary,
                    "goals": goals,
                    "promises": promises,
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/recent/{persona}", methods=["GET"])
    async def recent_memories(request: Request) -> JSONResponse:
        """Get recent memories for a persona."""
        persona = _resolve_persona_from_request(request)
        limit = int(request.query_params.get("limit", "10"))
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.memory_service.get_recent(limit=limit)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse(
                {
                    "persona": persona,
                    "memories": [_memory_to_dict(m) for m in result.value],
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/search/{persona}", methods=["GET"])
    async def search_memories(request: Request) -> JSONResponse:
        """Search memories for a persona."""
        persona = _resolve_persona_from_request(request)
        q = request.query_params.get("q", "")
        limit = int(request.query_params.get("limit", "20"))
        mode = request.query_params.get("mode", "hybrid")
        if mode not in ("semantic", "keyword", "hybrid", "smart"):
            mode = "hybrid"
        if not q:
            return JSONResponse({"error": "Query parameter 'q' is required"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            from memory_mcp.domain.search.engine import SearchQuery

            query = SearchQuery(text=q, mode=mode, top_k=limit)
            # Set persona for semantic search adapter if available
            if hasattr(ctx.search_engine, "_semantic") and ctx.search_engine._semantic is not None:
                ctx.search_engine._semantic._persona = persona  # noqa: SLF001

            result = ctx.search_engine.search(query)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse(
                {
                    "persona": persona,
                    "query": q,
                    "results": [
                        {
                            "memory": _memory_to_dict(r.memory),
                            "score": round(r.score, 4),
                            "source": r.source,
                        }
                        for r in result.value
                    ],
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/emotions/{persona}", methods=["GET"])
    async def emotion_history(request: Request) -> JSONResponse:
        """Get emotion history for a persona, grouped by date."""
        persona = _resolve_persona_from_request(request)
        days = int(request.query_params.get("days", "7"))
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.persona_repo.get_emotion_history_by_days(persona, days)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)

            # Group by date
            grouped: dict[str, list[dict]] = defaultdict(list)
            for record in result.value:
                date_str = record.timestamp.strftime("%Y-%m-%d") if record.timestamp else "unknown"
                grouped[date_str].append(
                    {
                        "emotion_type": record.emotion_type,
                        "intensity": record.intensity,
                        "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                        "trigger_memory_key": record.trigger_memory_key,
                        "context": record.context,
                    }
                )
            return JSONResponse(
                {
                    "persona": persona,
                    "days": days,
                    "history": dict(grouped),
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/observations/{persona}", methods=["GET"])
    async def observations(request: Request) -> JSONResponse:
        """Paginated memory observations with optional filtering."""
        persona = _resolve_persona_from_request(request)
        page = int(request.query_params.get("page", "1"))
        per_page = int(request.query_params.get("per_page", "20"))
        tag = request.query_params.get("tag") or None
        q = request.query_params.get("q") or None
        sort_order = request.query_params.get("sort", "desc")
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.memory_repo.find_with_pagination(
                page=page,
                per_page=per_page,
                tag=tag,
                query=q,
                sort_order=sort_order,
            )
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            memories, total_count = result.value
            total_pages = (total_count + per_page - 1) // per_page
            return JSONResponse(
                {
                    "persona": persona,
                    "page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "memories": [_memory_to_dict(m) for m in memories],
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/strengths/{persona}", methods=["GET"])
    async def memory_strengths(request: Request) -> JSONResponse:
        """Get all memory strengths with histogram distribution."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.memory_repo.get_all_strengths()
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)

            strengths = result.value
            # Build histogram (10 buckets: 0.0-0.1, 0.1-0.2, ..., 0.9-1.0)
            buckets = [0] * 10
            for s in strengths:
                idx = min(int(s.strength * 10), 9)
                buckets[idx] += 1
            histogram = [{"range": f"{i / 10:.1f}-{(i + 1) / 10:.1f}", "count": buckets[i]} for i in range(10)]

            return JSONResponse(
                {
                    "persona": persona,
                    "total": len(strengths),
                    "strengths": [_strength_to_dict(s) for s in strengths],
                    "histogram": histogram,
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/admin/rebuild/{persona}", methods=["POST"])
    async def rebuild_vectors(request: Request) -> JSONResponse:
        """Rebuild Qdrant vector collection for a persona (async, returns 202)."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        if ctx.vector_store is None:
            return JSONResponse({"error": "Vector store unavailable"}, status_code=503)
        try:
            # Run rebuild in background to avoid blocking
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, ctx.vector_store.rebuild_collection, persona)
            return JSONResponse(
                {"status": "accepted", "message": f"Rebuild started for '{persona}'"},
                status_code=202,
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    # ------------------------------------------------------------------
    # Settings management routes (3 endpoints)
    # ------------------------------------------------------------------

    @mcp.custom_route("/api/settings", methods=["GET"])
    async def get_settings(request: Request) -> JSONResponse:
        """Get all runtime settings with metadata."""
        try:
            from memory_mcp.config.runtime_config import RuntimeConfigManager

            config = RuntimeConfigManager()
            return JSONResponse(config.get_all())
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/settings", methods=["PUT"])
    async def update_settings(request: Request) -> JSONResponse:
        """Update a runtime setting."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        category = body.get("category")
        key = body.get("key")
        value = body.get("value")
        if not category or not key:
            return JSONResponse(
                {"error": "Fields 'category' and 'key' are required"},
                status_code=400,
            )
        try:
            from memory_mcp.config.runtime_config import RuntimeConfigManager

            config = RuntimeConfigManager()
            result = config.update(category, key, value)
            status_code = 200 if result.get("success") else 400
            return JSONResponse(result, status_code=status_code)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/settings/status", methods=["GET"])
    async def settings_status(request: Request) -> JSONResponse:
        """Get reload status for runtime settings."""
        try:
            from memory_mcp.config.runtime_config import RuntimeConfigManager

            config = RuntimeConfigManager()
            return JSONResponse(
                {
                    "reload_status": config.reload_status.get_all(),
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    # ------------------------------------------------------------------
    # Memory CRUD routes
    # ------------------------------------------------------------------

    @mcp.custom_route("/api/memories/{persona}", methods=["POST"])
    async def create_memory(request: Request) -> JSONResponse:
        """Create a new memory for a persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        content = body.get("content")
        if not content:
            return JSONResponse({"error": "Field 'content' is required"}, status_code=400)
        try:
            result = ctx.memory_service.create_memory(
                content=content,
                importance=body.get("importance", 0.5),
                emotion=body.get("emotion_type", "neutral"),
                emotion_intensity=body.get("emotion_intensity", 0.0),
                tags=body.get("tags"),
                privacy_level=body.get("privacy_level", "internal"),
                source_context=body.get("source_context"),
            )
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            # Index in vector store if available
            mem = result.value
            if ctx.vector_store is not None:
                with contextlib.suppress(Exception):
                    ctx.vector_store.upsert(persona, mem.key, mem.content)
            return JSONResponse(
                {"status": "ok", "memory": _memory_to_dict(mem)},
                status_code=201,
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/memories/{persona}/{key}", methods=["PUT"])
    async def update_memory(request: Request) -> JSONResponse:
        """Update an existing memory."""
        persona = _resolve_persona_from_request(request)
        key = request.path_params.get("key", "")
        if not key:
            return JSONResponse({"error": "Memory key is required"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        try:
            # Build updates dict from allowed fields
            allowed = {
                "content",
                "importance",
                "emotion_type",
                "emotion_intensity",
                "tags",
                "privacy_level",
                "source_context",
            }
            updates = {}
            for field in allowed:
                if field in body:
                    # Map emotion_type -> emotion for domain model
                    if field == "emotion_type":
                        updates["emotion"] = body[field]
                    else:
                        updates[field] = body[field]
            if not updates:
                return JSONResponse({"error": "No valid fields to update"}, status_code=400)
            result = ctx.memory_service.update_memory(key, **updates)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=404)
            # Re-index in vector store if content changed
            mem = result.value
            if "content" in updates and ctx.vector_store is not None:
                with contextlib.suppress(Exception):
                    ctx.vector_store.upsert(persona, mem.key, mem.content)
            return JSONResponse({"status": "ok", "memory": _memory_to_dict(mem)})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/memories/{persona}/{key}", methods=["DELETE"])
    async def delete_memory(request: Request) -> JSONResponse:
        """Delete a memory by key."""
        persona = _resolve_persona_from_request(request)
        key = request.path_params.get("key", "")
        if not key:
            return JSONResponse({"error": "Memory key is required"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.memory_service.delete_memory(key)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=404)
            # Remove from vector store if available
            if ctx.vector_store is not None:
                with contextlib.suppress(Exception):
                    ctx.vector_store.delete(persona, key)
            return JSONResponse({"status": "ok", "deleted": key})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    # ------------------------------------------------------------------
    # Inventory CRUD routes
    # ------------------------------------------------------------------

    def _item_to_dict(it) -> dict:
        """Convert an InventoryItem dataclass to a JSON-safe dict."""
        d = asdict(it)
        for k in ("created_at", "updated_at"):
            if k in d and d[k] is not None:
                d[k] = d[k].isoformat()
        return d

    @mcp.custom_route("/api/items/{persona}", methods=["GET"])
    async def list_items(request: Request) -> JSONResponse:
        """List all inventory items for a persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.equipment_service.search_items()
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse({"persona": persona, "items": [_item_to_dict(it) for it in result.value]})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/items/{persona}", methods=["POST"])
    async def add_item(request: Request) -> JSONResponse:
        """Add an item to the inventory for a persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        item_name = body.get("item_name")
        if not item_name:
            return JSONResponse({"error": "Field 'item_name' is required"}, status_code=400)
        try:
            result = ctx.equipment_service.add_item(
                item_name,
                body.get("category"),
                body.get("description"),
                body.get("quantity", 1),
                body.get("tags"),
            )
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse({"status": "ok", "item_name": item_name}, status_code=201)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/items/{persona}/equip", methods=["POST"])
    async def equip_items(request: Request) -> JSONResponse:
        """Change equipment slots for a persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        if not isinstance(body, dict) or not body:
            return JSONResponse({"error": "Body must be a non-empty dict of {slot: item_name}"}, status_code=400)
        auto_add = body.pop("auto_add", True)
        if not body:
            return JSONResponse({"error": "No equipment slots provided"}, status_code=400)
        try:
            result = ctx.equipment_service.equip(body, auto_add)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse({"status": "ok", "equipped": body})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/items/{persona}/unequip", methods=["POST"])
    async def unequip_items(request: Request) -> JSONResponse:
        """Unequip slots for a persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        slots = body.get("slots", [])
        if isinstance(slots, str):
            slots = [slots]
        if not slots:
            return JSONResponse({"error": "Field 'slots' is required"}, status_code=400)
        try:
            result = ctx.equipment_service.unequip(slots)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse({"status": "ok", "unequipped": slots})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/items/{persona}/{item_name}", methods=["PUT"])
    async def update_item(request: Request) -> JSONResponse:
        """Update an inventory item for a persona."""
        persona = _resolve_persona_from_request(request)
        item_name = request.path_params.get("item_name", "")
        if not item_name:
            return JSONResponse({"error": "Item name is required"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        allowed = {"category", "description", "quantity", "tags"}
        updates = {k: v for k, v in body.items() if k in allowed}
        if not updates:
            return JSONResponse({"error": "No valid fields to update"}, status_code=400)
        try:
            result = ctx.equipment_service.update_item(item_name, **updates)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse({"status": "ok", "item_name": item_name})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/items/{persona}/{item_name}", methods=["DELETE"])
    async def delete_item(request: Request) -> JSONResponse:
        """Delete an inventory item for a persona."""
        persona = _resolve_persona_from_request(request)
        item_name = request.path_params.get("item_name", "")
        if not item_name:
            return JSONResponse({"error": "Item name is required"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.equipment_service.remove_item(item_name)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            return JSONResponse({"status": "ok", "deleted": item_name})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    # ------------------------------------------------------------------
    # Graph data routes
    # ------------------------------------------------------------------

    @mcp.custom_route("/api/graph/{persona}", methods=["GET"])
    async def graph_data(request: Request) -> JSONResponse:
        """Get memory graph data (nodes and edges) for visualization."""
        persona = _resolve_persona_from_request(request)
        limit = int(request.query_params.get("limit", "200"))
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            result = ctx.memory_repo.find_recent(limit=limit)
            if not result.is_ok:
                return JSONResponse({"error": str(result.error)}, status_code=500)
            memories = result.value

            nodes = []
            edges = []
            edge_set = set()  # Deduplicate edges
            tag_to_keys: dict[str, list[str]] = defaultdict(list)

            for mem in memories:
                nodes.append(
                    {
                        "key": mem.key,
                        "content": mem.content[:100] if mem.content else "",
                        "tags": mem.tags or [],
                        "emotion_type": mem.emotion,
                        "importance": mem.importance,
                    }
                )
                # Track tag -> memory key mapping for co-occurrence edges
                for tag in mem.tags or []:
                    tag_to_keys[tag].append(mem.key)
                # Edges from related_keys
                for related in mem.related_keys or []:
                    pair = tuple(sorted([mem.key, related]))
                    if pair not in edge_set:
                        edge_set.add(pair)
                        edges.append(
                            {
                                "source": mem.key,
                                "target": related,
                                "type": "related",
                            }
                        )

            # Edges from tag co-occurrence
            for tag, keys in tag_to_keys.items():
                if len(keys) > 1:
                    # Limit co-occurrence edges for tags with many memories
                    capped = keys[:20]
                    for i in range(len(capped)):
                        for j in range(i + 1, len(capped)):
                            pair = tuple(sorted([capped[i], capped[j]]))
                            if pair not in edge_set:
                                edge_set.add(pair)
                                edges.append(
                                    {
                                        "source": capped[i],
                                        "target": capped[j],
                                        "type": "tag",
                                        "tag": tag,
                                    }
                                )

            return JSONResponse(
                {
                    "persona": persona,
                    "nodes": nodes,
                    "edges": edges,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    # ------------------------------------------------------------------
    # Import / Export routes
    # ------------------------------------------------------------------

    @mcp.custom_route("/api/import/{persona}", methods=["POST"])
    async def import_data(request: Request) -> JSONResponse:
        """Import persona data from a ZIP file upload."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            form = await request.form()
            upload = form.get("file")
            if upload is None:
                return JSONResponse({"error": "No file uploaded. Use multipart form field 'file'."}, status_code=400)
            file_bytes = await upload.read()
            if not file_bytes:
                return JSONResponse({"error": "Uploaded file is empty"}, status_code=400)

            # Save to temp location within data directory
            settings = Settings()
            import_dir = Path(settings.import_dir)
            import_dir.mkdir(parents=True, exist_ok=True)
            zip_path = import_dir / f"_upload_{persona}.zip"
            zip_path.write_bytes(file_bytes)

            try:
                from memory_mcp.migration.importers.legacy_importer import LegacyImporter

                importer = LegacyImporter(ctx.connection, persona)
                result = importer.import_from_zip(str(zip_path))
                if not result.is_ok:
                    return JSONResponse({"error": str(result.error)}, status_code=500)
                return JSONResponse(
                    {
                        "status": "ok",
                        "persona": persona,
                        "imported": result.value,
                    }
                )
            finally:
                # Clean up uploaded zip
                if zip_path.exists():
                    zip_path.unlink()
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/export/{persona}", methods=["GET"])
    async def export_data(request: Request) -> StreamingResponse:
        """Export persona data as a ZIP file download."""
        persona = _resolve_persona_from_request(request)
        settings = Settings()
        persona_dir = Path(settings.data_dir) / persona
        if not persona_dir.exists():
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in persona_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(persona_dir))
                        zf.write(file_path, arcname)
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{persona}_export.zip"'},
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    # ------------------------------------------------------------------
    # Persona management routes
    # ------------------------------------------------------------------

    @mcp.custom_route("/api/personas", methods=["POST"])
    async def create_persona(request: Request) -> JSONResponse:
        """Create a new persona with initialized databases."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        persona_name = body.get("name")
        if not persona_name:
            return JSONResponse({"error": "Field 'name' is required"}, status_code=400)
        # Validate name (alphanumeric, hyphens, underscores)
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", persona_name):
            return JSONResponse(
                {"error": "Persona name must contain only alphanumeric characters, hyphens, and underscores"},
                status_code=400,
            )
        settings = Settings()
        persona_dir = Path(settings.data_dir) / persona_name
        if persona_dir.exists():
            return JSONResponse({"error": f"Persona '{persona_name}' already exists"}, status_code=409)
        try:
            # Initialize by getting context (this creates dirs and schema)
            ctx = AppContextRegistry.get(persona_name)
            if ctx is None:
                return JSONResponse({"error": "Failed to initialize persona"}, status_code=500)
            return JSONResponse(
                {"status": "ok", "persona": persona_name, "message": f"Persona '{persona_name}' created"},
                status_code=201,
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/personas/{persona}", methods=["DELETE"])
    async def delete_persona(request: Request) -> JSONResponse:
        """Delete a persona and all its data."""
        persona = _resolve_persona_from_request(request)
        if persona == "default":
            return JSONResponse({"error": "Cannot delete the default persona"}, status_code=403)
        settings = Settings()
        persona_dir = Path(settings.data_dir) / persona
        if not persona_dir.exists():
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            # Close connections if cached
            if persona in AppContextRegistry._contexts:
                AppContextRegistry._contexts[persona].close()
                del AppContextRegistry._contexts[persona]
            # Remove directory
            shutil.rmtree(persona_dir)
            return JSONResponse({"status": "ok", "deleted": persona})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/personas/{persona}/profile", methods=["PUT"])
    async def update_persona_profile(request: Request) -> JSONResponse:
        """Update persona profile (user_info, persona_info, relationship)."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        try:
            updated = []
            if "user_info" in body and isinstance(body["user_info"], dict):
                result = ctx.persona_service.update_user_info(persona, body["user_info"])
                if result.is_ok:
                    updated.append("user_info")
            if "persona_info" in body and isinstance(body["persona_info"], dict):
                result = ctx.persona_service.update_persona_info(persona, body["persona_info"])
                if result.is_ok:
                    updated.append("persona_info")
            if "relationship_status" in body:
                result = ctx.persona_service.update_relationship(persona, body["relationship_status"])
                if result.is_ok:
                    updated.append("relationship_status")
            if not updated:
                return JSONResponse({"error": "No valid fields to update"}, status_code=400)
            return JSONResponse({"status": "ok", "updated": updated})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/blocks/{persona}", methods=["GET"])
    async def list_blocks(request: Request) -> JSONResponse:
        """List all memory blocks for a persona."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"blocks": []})
        result = ctx.memory_service.list_blocks()
        blocks = result.value if result.is_ok else []
        return JSONResponse({"persona": persona, "blocks": blocks})

    @mcp.custom_route("/api/blocks/{persona}", methods=["POST"])
    async def create_block(request: Request) -> JSONResponse:
        """Create or update a memory block."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        block_name = body.get("block_name", "").strip()
        content = body.get("content", "").strip()
        if not block_name or not content:
            return JSONResponse({"error": "block_name and content required"}, status_code=400)
        result = ctx.memory_service.write_block(
            block_name,
            content,
            block_type=body.get("block_type", "custom"),
            max_tokens=body.get("max_tokens"),
            priority=body.get("priority", 0),
        )
        if result.is_ok:
            return JSONResponse({"ok": True, "block_name": block_name})
        return JSONResponse({"error": str(result.error)}, status_code=500)

    @mcp.custom_route("/api/blocks/{persona}/{block_name}", methods=["DELETE"])
    async def delete_block_endpoint(request: Request) -> JSONResponse:
        """Delete a memory block."""
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if not ctx:
            return JSONResponse({"error": "Persona not found"}, status_code=404)
        block_name = request.path_params.get("block_name", "")
        result = ctx.memory_service.delete_block(block_name)
        if result.is_ok:
            return JSONResponse({"ok": True})
        return JSONResponse({"error": str(result.error)}, status_code=500)
