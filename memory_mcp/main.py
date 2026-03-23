from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from memory_mcp.api.http.routes import register_http_routes
from memory_mcp.api.mcp.tools import register_tools
from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.config.settings import Settings
from memory_mcp.infrastructure.logging.structured import get_logger, setup_logging


def create_app() -> FastMCP:
    """Create and configure the FastMCP application."""
    settings = Settings()
    setup_logging(settings.log_level)
    logger = get_logger("main")

    logger.info("Starting MemoryMCP v2.0.0 on %s:%s", settings.server.host, settings.server.port)

    AppContextRegistry.configure(settings)

    mcp = FastMCP(
        "MemoryMCP",
        stateless_http=True,
    )

    register_tools(mcp)
    register_http_routes(mcp)

    return mcp


mcp = create_app()


def main() -> None:
    """Run the MemoryMCP server."""
    settings = Settings()
    mcp.run(
        transport="streamable-http",
        host=settings.server.host,
        port=settings.server.port,
    )


if __name__ == "__main__":
    main()
