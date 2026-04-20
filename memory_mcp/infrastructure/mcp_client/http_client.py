from __future__ import annotations

import asyncio

from memory_mcp.infrastructure.logging.structured import get_logger
from memory_mcp.infrastructure.mcp_client.types import MCPServerConfig, MCPTool

logger = get_logger(__name__)


async def list_tools(config: MCPServerConfig) -> list[MCPTool]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _inner() -> list[MCPTool]:
        async with (
            streamablehttp_client(config.url, headers=config.headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.list_tools()
            tools = []
            for tool in result.tools:
                tools.append(
                    MCPTool(
                        name=f"{config.name}__{tool.name}",
                        description=tool.description or "",
                        input_schema=tool.inputSchema if tool.inputSchema else {},
                        server_name=config.name,
                        original_name=tool.name,
                    )
                )
            return tools

    try:
        return await asyncio.wait_for(_inner(), timeout=30.0)
    except Exception as e:
        logger.warning("http_client list_tools failed (%s): %s", config.url, e)
        return []


async def call_tool(config: MCPServerConfig, tool_name: str, args: dict) -> dict:
    """tool_name は original_name（プレフィックスなし）"""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _inner() -> dict:
        async with (
            streamablehttp_client(config.url, headers=config.headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            content_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    content_parts.append(item.text)
                else:
                    content_parts.append(str(item))
            return {"result": "\n".join(content_parts), "isError": result.isError}

    try:
        return await asyncio.wait_for(_inner(), timeout=30.0)
    except Exception as e:
        logger.warning("http_client call_tool failed (%s/%s): %s", config.url, tool_name, e)
        return {"error": str(e)}
