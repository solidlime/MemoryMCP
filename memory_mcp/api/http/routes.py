from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from starlette.requests import Request  # noqa: TC002
from starlette.responses import HTMLResponse, JSONResponse  # noqa: TC002

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
        """Serve the dashboard HTML page."""
        from memory_mcp.api.http.dashboard import render_dashboard

        return HTMLResponse(render_dashboard())

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

            # Strengths summary
            strength_result = ctx.memory_repo.get_all_strengths()
            strengths_raw = strength_result.value if strength_result.is_ok else []
            strength_values = [s.strength for s in strengths_raw]
            strengths_summary = {
                "total": len(strength_values),
                "avg": round(sum(strength_values) / len(strength_values), 3) if strength_values else 0,
                "min": round(min(strength_values), 3) if strength_values else 0,
                "max": round(max(strength_values), 3) if strength_values else 0,
            }

            # Goals & Promises
            goals_result = ctx.memory_repo.get_goals()
            goals = goals_result.value if goals_result.is_ok else []

            promises_result = ctx.memory_repo.get_promises()
            promises = promises_result.value if promises_result.is_ok else []

            return JSONResponse(
                {
                    "persona": persona,
                    "stats": stats,
                    "context": context,
                    "recent": recent,
                    "blocks": blocks,
                    "equipment": equipment,
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
        if not q:
            return JSONResponse({"error": "Query parameter 'q' is required"}, status_code=400)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            from memory_mcp.domain.search.engine import SearchQuery

            query = SearchQuery(text=q, mode="hybrid", top_k=limit)
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
            loop = asyncio.get_event_loop()
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
