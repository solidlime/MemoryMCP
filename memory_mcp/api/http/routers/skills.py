from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

from memory_mcp.api.http.deps import _safe_get_context
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)

_DEFAULT_PERSONA = "default"


def _get_db():
    ctx = _safe_get_context(_DEFAULT_PERSONA)
    if not ctx:
        return None
    return ctx.connection.get_memory_db()


def register_skills_routes(mcp) -> None:

    @mcp.custom_route("/api/skills", methods=["GET"])
    async def list_skills(request: Request) -> JSONResponse:
        db = _get_db()
        if db is None:
            return JSONResponse({"error": "Context not available"}, status_code=503)
        from memory_mcp.domain.skill import SkillRepository

        repo = SkillRepository(db)
        skills = repo.list_all()
        return JSONResponse([s.model_dump() for s in skills])

    @mcp.custom_route("/api/skills", methods=["POST"])
    async def create_skill(request: Request) -> JSONResponse:
        db = _get_db()
        if db is None:
            return JSONResponse({"error": "Context not available"}, status_code=503)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "name is required"}, status_code=400)
        from memory_mcp.domain.skill import Skill, SkillRepository

        repo = SkillRepository(db)
        skill = Skill(name=name, description=body.get("description", ""), content=body.get("content", ""))
        saved = repo.upsert(skill)
        return JSONResponse(saved.model_dump(), status_code=201)

    @mcp.custom_route("/api/skills/{name}", methods=["PUT"])
    async def update_skill(request: Request) -> JSONResponse:
        name = request.path_params.get("name", "")
        db = _get_db()
        if db is None:
            return JSONResponse({"error": "Context not available"}, status_code=503)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        from memory_mcp.domain.skill import Skill, SkillRepository

        repo = SkillRepository(db)
        existing = repo.get(name)
        if not existing:
            return JSONResponse({"error": "Skill not found"}, status_code=404)
        updated = Skill(
            id=existing.id,
            name=name,
            description=body.get("description", existing.description),
            content=body.get("content", existing.content),
            created_at=existing.created_at,
        )
        saved = repo.save(updated)
        return JSONResponse(saved.model_dump())

    @mcp.custom_route("/api/skills/{name}", methods=["DELETE"])
    async def delete_skill(request: Request) -> JSONResponse:
        name = request.path_params.get("name", "")
        db = _get_db()
        if db is None:
            return JSONResponse({"error": "Context not available"}, status_code=503)
        from memory_mcp.domain.skill import SkillRepository

        repo = SkillRepository(db)
        existing = repo.get(name)
        if not existing:
            return JSONResponse({"error": "Skill not found"}, status_code=404)
        repo.delete(name)
        return JSONResponse({"status": "deleted"})

    @mcp.custom_route("/api/skills/sync", methods=["POST"])
    async def sync_skills(request: Request) -> JSONResponse:
        """ファイルシステムの data/skills/<name>/SKILL.md をDBに同期する。"""
        db = _get_db()
        if db is None:
            return JSONResponse({"error": "Context not available"}, status_code=503)
        from memory_mcp.config.settings import get_settings
        from memory_mcp.domain.skill import SkillRepository

        repo = SkillRepository(db)
        synced = repo.load_from_dir(get_settings().skills_dir)
        return JSONResponse({"synced": len(synced), "skills": [s.name for s in synced]})
