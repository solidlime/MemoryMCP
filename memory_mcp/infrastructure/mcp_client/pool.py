from __future__ import annotations

import asyncio
import contextlib

from memory_mcp.infrastructure.logging.structured import get_logger
from memory_mcp.infrastructure.mcp_client.types import MCPServerConfig, MCPTool

logger = get_logger(__name__)


class MCPClientPool:
    """MCPサーバー群を管理するプール。async context managerとして使用。"""

    def __init__(self, server_configs: list[dict]) -> None:
        self._configs: list[MCPServerConfig] = []
        for cfg in server_configs:
            with contextlib.suppress(Exception):
                self._configs.append(MCPServerConfig.model_validate(cfg))
        self._tools: list[MCPTool] = []

    async def __aenter__(self) -> MCPClientPool:
        tasks = [self._fetch_tools(cfg) for cfg in self._configs if cfg.enabled]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                self._tools.extend(r)
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def _fetch_tools(self, config: MCPServerConfig) -> list[MCPTool]:
        try:
            if config.transport == "http":
                from memory_mcp.infrastructure.mcp_client.http_client import list_tools
            else:
                from memory_mcp.infrastructure.mcp_client.stdio_client import list_tools
            return await list_tools(config)
        except Exception as e:
            logger.warning("MCPClientPool: failed to fetch tools from %s: %s", config.name, e)
            return []

    def list_all_tools(self) -> list:
        """全サーバーのツールをToolDefinitionリストとして返す。"""
        from memory_mcp.infrastructure.llm.base import ToolDefinition

        return [
            ToolDefinition(
                name=tool.name,
                description=f"[{tool.server_name}] {tool.description}",
                input_schema=tool.input_schema,
            )
            for tool in self._tools
        ]

    async def call_tool(self, qualified_name: str, args: dict) -> dict:
        """qualified_name = "{server_name}__{tool_name}" でルーティング。"""
        if "__" not in qualified_name:
            return {"error": f"Invalid qualified tool name: {qualified_name}"}
        server_name, tool_name = qualified_name.split("__", 1)
        config = next((c for c in self._configs if c.name == server_name), None)
        if not config:
            return {"error": f"MCP server not found: {server_name}"}
        try:
            if config.transport == "http":
                from memory_mcp.infrastructure.mcp_client.http_client import call_tool
            else:
                from memory_mcp.infrastructure.mcp_client.stdio_client import call_tool
            return await call_tool(config, tool_name, args)
        except Exception as e:
            logger.warning("MCPClientPool: call_tool failed %s: %s", qualified_name, e)
            return {"error": str(e)}
