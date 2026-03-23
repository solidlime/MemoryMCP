from __future__ import annotations

import os

from starlette.requests import Request  # noqa: TC002
from starlette.responses import JSONResponse  # noqa: TC002

from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.config.settings import Settings


def register_http_routes(app) -> None:
    """Register HTTP routes on the Starlette app."""

    @app.route("/health")
    async def health(request: Request) -> JSONResponse:
        """Health check endpoint."""
        ctx = AppContextRegistry.get("default")
        qdrant_ok = ctx.vector_store is not None
        return JSONResponse(
            {
                "status": "ok",
                "version": "2.0.0",
                "qdrant": "connected" if qdrant_ok else "unavailable",
            }
        )

    @app.route("/api/personas")
    async def list_personas(request: Request) -> JSONResponse:
        """List available personas by scanning data directory."""
        settings = Settings()
        data_dir = settings.data_dir
        personas: list[str] = []
        if os.path.exists(data_dir):
            for d in os.listdir(data_dir):
                if os.path.isdir(os.path.join(data_dir, d)) and not d.startswith("_"):
                    personas.append(d)
        return JSONResponse({"personas": personas})

    @app.route("/api/stats/{persona}")
    async def persona_stats(request: Request) -> JSONResponse:
        """Get stats for a specific persona."""
        persona = request.path_params["persona"]
        ctx = AppContextRegistry.get(persona)
        stats = ctx.memory_service.get_stats()
        return JSONResponse(stats.value if stats.is_ok else {"error": str(stats.error)})
