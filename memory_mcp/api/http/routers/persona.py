from __future__ import annotations

import shutil
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.responses import HTMLResponse, JSONResponse

from memory_mcp.api.http.deps import (
    _PERSONA_PATTERN,
    _memory_to_dict,
    _resolve_persona_from_request,
    _safe_get_context,
)
from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.config.settings import Settings

if TYPE_CHECKING:
    from starlette.requests import Request


def register_persona_routes(mcp) -> None:
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
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
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        stats = ctx.memory_service.get_stats()
        return JSONResponse(stats.value if stats.is_ok else {"error": str(stats.error)})

    @mcp.custom_route("/", methods=["GET"])
    async def dashboard_page(request: Request) -> HTMLResponse:
        from memory_mcp.api.http.dashboard import render_dashboard

        return HTMLResponse(render_dashboard())

    @mcp.custom_route("/dashboard/{persona}", methods=["GET"])
    async def dashboard_page_persona(request: Request) -> HTMLResponse:
        from memory_mcp.api.http.dashboard import render_dashboard

        persona = _resolve_persona_from_request(request)
        return HTMLResponse(render_dashboard(persona))

    @mcp.custom_route("/api/dashboard/{persona}", methods=["GET"])
    async def dashboard_data(request: Request) -> JSONResponse:
        persona = _resolve_persona_from_request(request)
        ctx = _safe_get_context(persona)
        if ctx is None:
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            stats_result = ctx.memory_service.get_stats()
            stats = stats_result.value if stats_result.is_ok else {}

            context_result = ctx.persona_service.get_context(persona)
            context = asdict(context_result.value) if context_result.is_ok else {}
            if "last_conversation_time" in context and context["last_conversation_time"] is not None:
                context["last_conversation_time"] = context["last_conversation_time"].isoformat()

            recent_result = ctx.memory_service.get_recent(limit=5)
            recent = [_memory_to_dict(m) for m in recent_result.value] if recent_result.is_ok else []

            blocks_result = ctx.memory_service.list_blocks()
            blocks = blocks_result.value if blocks_result.is_ok else []

            equip_result = ctx.equipment_service.get_equipment()
            equipment = equip_result.value if equip_result.is_ok else {}

            items_result = ctx.equipment_service.search_items()
            items_raw = items_result.value if items_result.is_ok else []
            items = []
            for it in items_raw:
                d = asdict(it)
                for k in ("created_at", "updated_at"):
                    if k in d and d[k] is not None:
                        d[k] = d[k].isoformat()
                items.append(d)

            strength_result = ctx.memory_repo.get_all_strengths()
            strengths_raw = strength_result.value if strength_result.is_ok else []
            strength_values = [s.strength for s in strengths_raw]
            strengths_summary = {
                "total": len(strength_values),
                "avg": round(sum(strength_values) / len(strength_values), 3) if strength_values else None,
                "min": round(min(strength_values), 3) if strength_values else None,
                "max": round(max(strength_values), 3) if strength_values else None,
            }

            goals_result = ctx.memory_repo.get_goals()
            goals = goals_result.value if goals_result.is_ok else []

            promises_result = ctx.memory_repo.get_promises()
            promises = promises_result.value if promises_result.is_ok else []

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

    @mcp.custom_route("/api/personas", methods=["POST"])
    async def create_persona(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        persona_name = body.get("name")
        if not persona_name:
            return JSONResponse({"error": "Field 'name' is required"}, status_code=400)
        if not _PERSONA_PATTERN.match(persona_name):
            return JSONResponse(
                {"error": "Persona name must contain only alphanumeric characters, hyphens, and underscores"},
                status_code=400,
            )
        settings = Settings()
        persona_dir = Path(settings.data_dir) / persona_name
        if persona_dir.exists():
            return JSONResponse({"error": f"Persona '{persona_name}' already exists"}, status_code=409)
        try:
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
        persona = _resolve_persona_from_request(request)
        if persona == "default":
            return JSONResponse({"error": "Cannot delete the default persona"}, status_code=403)
        settings = Settings()
        persona_dir = Path(settings.data_dir) / persona
        if not persona_dir.exists():
            return JSONResponse({"error": f"Persona '{persona}' not found"}, status_code=404)
        try:
            if persona in AppContextRegistry._contexts:
                AppContextRegistry._contexts[persona].close()
                del AppContextRegistry._contexts[persona]
            shutil.rmtree(persona_dir)
            return JSONResponse({"status": "ok", "deleted": persona})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @mcp.custom_route("/api/personas/{persona}/profile", methods=["PUT"])
    async def update_persona_profile(request: Request) -> JSONResponse:
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
