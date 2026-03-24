from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from memory_mcp.api.http.routes import register_http_routes
from memory_mcp.api.mcp.middleware import PersonaMiddleware
from memory_mcp.api.mcp.tools import register_tools
from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.config.settings import Settings
from memory_mcp.infrastructure.logging.structured import get_logger, setup_logging


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
    )

    # Auto-import on startup
    if settings.import_dir:
        try:
            from memory_mcp.application.auto_import import run_auto_import

            results = run_auto_import(settings)
            if results:
                for persona, counts in results.items():
                    logger.info("Auto-imported persona '%s': %s", persona, counts)
        except Exception:
            logger.exception("Auto-import failed")

    register_tools(mcp)
    register_http_routes(mcp)

    return mcp


mcp = create_app()


def main() -> None:
    """Run the MemoryMCP server."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
