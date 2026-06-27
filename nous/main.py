from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from starlette.requests import Request

from nous.api.http.routes import register_http_routes
from nous.api.mcp.middleware import PersonaMiddleware
from nous.api.mcp.tools import register_tools
from nous.application.sandbox.service import _sessions as sandbox_sessions
from nous.application.sandbox.service import close_sandbox_session
from nous.application.use_cases import AppContextRegistry
from nous.config.settings import Settings
from nous.infrastructure.logging.structured import get_logger, setup_logging


class MemoryFastMCP(FastMCP):
    """FastMCP subclass that injects PersonaMiddleware for header-based persona resolution."""

    def streamable_http_app(self):
        app = super().streamable_http_app()
        app.add_middleware(PersonaMiddleware)
        return app

    def sse_app(self, mount_path=None):
        app = super().sse_app(mount_path)
        app.add_middleware(PersonaMiddleware)
        return app


def _mount_static_files(mcp: MemoryFastMCP) -> None:
    """Mount /static/ route for dashboard CSS/JS assets."""
    import mimetypes

    from starlette.responses import FileResponse, Response

    static_dir = Path(__file__).resolve().parent / "api" / "http" / "static"

    @mcp.custom_route("/static/{filepath:path}", methods=["GET", "HEAD"])
    async def serve_static(request: Request):  # noqa: F821
        filepath = request.path_params.get("filepath", "").lstrip("/")
        safe_path = os.path.normpath(filepath).replace("\\", "/").lstrip("/")
        if ".." in safe_path.split("/"):
            return Response("Forbidden", status_code=403)

        full_path = static_dir / safe_path
        if not full_path.is_file():
            return Response("Not Found", status_code=404)

        mime_type, _ = mimetypes.guess_type(str(full_path))
        return FileResponse(str(full_path), media_type=mime_type or "application/octet-stream")


def create_app() -> MemoryFastMCP:
    """Create and configure the FastMCP application."""
    settings = Settings()
    setup_logging(settings.log_level)
    logger = get_logger("main")

    logger.info("Starting MemoryMCP v2.0.0 on %s:%s", settings.server.host, settings.server.port)

    AppContextRegistry.configure(settings)

    # ディレクトリ構造を確保
    settings.ensure_directories()

    # キャッシュ環境変数を自動設定（未設定の場合のみ）
    os.environ.setdefault("HF_HOME", str(Path(settings.cache_dir) / "huggingface"))
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(Path(settings.cache_dir) / "sentence_transformers"))
    os.environ.setdefault("TORCH_HOME", str(Path(settings.cache_dir) / "torch"))

    mcp = MemoryFastMCP(
        "MemoryMCP",
        host=settings.server.host,
        port=settings.server.port,
        stateless_http=True,
        json_response=True,  # Accept: application/json のみでOK（SSE不要）
    )

    # Auto-import on startup
    if settings.import_dir:
        try:
            from nous.application.auto_import import run_auto_import

            results = run_auto_import(settings)
            if results:
                for persona, counts in results.items():
                    logger.info("Auto-imported persona '%s': %s", persona, counts)
        except Exception:
            logger.exception("Auto-import failed")

    register_tools(mcp)
    register_http_routes(mcp)

    # Mount static files for dashboard CSS/JS
    _mount_static_files(mcp)

    # Health check endpoint (docker-compose healthcheck)
    @mcp.custom_route("/health", methods=["GET", "HEAD"])
    async def health(request: Request):  # type: ignore[no-redef]  # noqa: F811
        import json as _json

        from starlette.responses import Response

        status = {"status": "healthy", "services": {}}

        # Check Qdrant
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url=settings.qdrant.url, api_key=settings.qdrant.api_key)
            client.get_collections()
            status["services"]["qdrant"] = "ok"
        except Exception as e:
            status["services"]["qdrant"] = f"error: {e}"
            status["status"] = "degraded"

        # Check SearXNG (non-critical)
        try:
            import httpx

            searxng_url = os.environ.get("NOUS_SEARXNG_URL", os.environ.get("SEARXNG_URL", "http://searxng:8080"))
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{searxng_url}/healthz")
                status["services"]["searxng"] = "ok" if r.status_code < 500 else f"error: HTTP {r.status_code}"
        except Exception as e:
            status["services"]["searxng"] = f"unreachable: {e}"

        # Check sandbox (non-critical)
        if settings.sandbox.enabled:
            try:
                from nous.application.sandbox.service import _ensure_sandbox_image

                _ensure_sandbox_image(settings.sandbox.image, "Dockerfile.sandbox")
                status["services"]["sandbox"] = "ok"
            except Exception as e:
                status["services"]["sandbox"] = f"error: {e}"

        return Response(
            _json.dumps(status, ensure_ascii=False),
            media_type="application/json",
            status_code=200 if status["status"] == "healthy" else 503,
        )

    # Mount static files for dashboard CSS/JS
    _mount_static_files(mcp)

    # Auto-sync skills from filesystem at startup
    try:
        from nous.domain.skill import SkillRepository
        from nous.infrastructure.sqlite.connection import get_global_skills_db

        skills_db = get_global_skills_db(settings.data_root)
        skill_repo = SkillRepository(skills_db)
        synced = skill_repo.load_from_dir(settings.skills_dir)
        if synced:
            logger.info("Auto-synced %d skills from %s", len(synced), settings.skills_dir)
    except Exception:
        logger.exception("Skills auto-sync failed")

    # Start background workers
    if settings.summarization.enabled:
        from nous.application.workers import SummarizationWorker

        summarization_worker = SummarizationWorker(settings)
        summarization_worker.start()

    # Start MemoRAG context snapshot worker
    if settings.memorag.enabled:
        from nous.application.workers.context_snapshot_worker import ContextSnapshotWorker

        snapshot_worker = ContextSnapshotWorker(settings)
        snapshot_worker.start()

    # Pre-warm sandbox Docker image in background to avoid blocking the
    # first sandbox request with a long image pull/build (~500MB download).
    if settings.sandbox.enabled:
        import threading

        def _prewarm_sandbox() -> None:
            try:
                from nous.application.sandbox.service import _ensure_sandbox_image

                logger.info("Pre-warming sandbox image %s in background...", settings.sandbox.image)
                _ensure_sandbox_image(settings.sandbox.image, "Dockerfile.sandbox")
                logger.info("Sandbox image pre-warm complete: %s", settings.sandbox.image)
            except Exception:
                logger.warning(
                    "Sandbox pre-warm failed (will retry on first use): %s", settings.sandbox.image, exc_info=True
                )

        threading.Thread(target=_prewarm_sandbox, daemon=True, name="sandbox-prewarm").start()

    # Register sandbox session cleanup on shutdown
    import atexit

    def _shutdown_sandbox_sessions() -> None:
        for persona in list(sandbox_sessions.keys()):
            with contextlib.suppress(Exception):
                close_sandbox_session(persona)

    atexit.register(_shutdown_sandbox_sessions)

    return mcp


mcp = create_app()


def main() -> None:
    """Run the MemoryMCP server."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
