from __future__ import annotations

import pytest

from memory_mcp.infrastructure.mcp_client.types import MCPServerConfig, MCPTool


class TestMCPServerConfig:
    def test_defaults(self):
        cfg = MCPServerConfig(name="test")
        assert cfg.transport == "http"
        assert cfg.url == ""
        assert cfg.command == ""
        assert cfg.args == []
        assert cfg.headers == {}
        assert cfg.enabled is True

    def test_http_config(self):
        cfg = MCPServerConfig(name="fs", transport="http", url="http://localhost:3000/mcp")
        assert cfg.transport == "http"
        assert cfg.url == "http://localhost:3000/mcp"

    def test_stdio_config(self):
        cfg = MCPServerConfig(name="git", transport="stdio", command="npx", args=["-y", "some-package"])
        assert cfg.transport == "stdio"
        assert cfg.command == "npx"
        assert cfg.args == ["-y", "some-package"]

    def test_disabled(self):
        cfg = MCPServerConfig(name="x", enabled=False)
        assert cfg.enabled is False

    def test_model_validate_from_dict(self):
        cfg = MCPServerConfig.model_validate({"name": "test", "transport": "http", "url": "http://x"})
        assert cfg.name == "test"


class TestMCPTool:
    def test_defaults(self):
        tool = MCPTool(name="fs__read_file")
        assert tool.description == ""
        assert tool.input_schema == {}
        assert tool.server_name == ""
        assert tool.original_name == ""

    def test_qualified_name(self):
        tool = MCPTool(name="myserver__do_thing", server_name="myserver", original_name="do_thing")
        assert tool.name == "myserver__do_thing"
        assert tool.server_name == "myserver"
        assert tool.original_name == "do_thing"


class TestMCPClientPool:
    @pytest.mark.asyncio
    async def test_empty_pool(self):
        from memory_mcp.infrastructure.mcp_client.pool import MCPClientPool

        async with MCPClientPool([]) as pool:
            tools = pool.list_all_tools()
            assert tools == []

    @pytest.mark.asyncio
    async def test_invalid_config_ignored(self):
        from memory_mcp.infrastructure.mcp_client.pool import MCPClientPool

        # invalid dict (missing required 'name') should be silently ignored
        async with MCPClientPool([{"transport": "http"}]) as pool:
            assert pool._configs == []

    @pytest.mark.asyncio
    async def test_disabled_server_skipped(self):
        from memory_mcp.infrastructure.mcp_client.pool import MCPClientPool

        cfg = {"name": "test", "transport": "http", "url": "http://localhost:9999", "enabled": False}
        async with MCPClientPool([cfg]) as pool:
            # disabled server → no tools fetched
            assert pool._tools == []

    @pytest.mark.asyncio
    async def test_list_all_tools_returns_tool_definitions(self):
        from unittest.mock import AsyncMock, patch

        from memory_mcp.infrastructure.mcp_client.pool import MCPClientPool
        from memory_mcp.infrastructure.mcp_client.types import MCPTool

        cfg = {"name": "myserver", "transport": "http", "url": "http://localhost:9999", "enabled": True}

        mock_tools = [
            MCPTool(name="myserver__do_thing", description="Does thing", input_schema={"type": "object"}, server_name="myserver", original_name="do_thing")
        ]

        with patch("memory_mcp.infrastructure.mcp_client.pool.MCPClientPool._fetch_tools", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_tools
            async with MCPClientPool([cfg]) as pool:
                tools = pool.list_all_tools()
                assert len(tools) == 1
                assert tools[0].name == "myserver__do_thing"
                assert "[myserver]" in tools[0].description

    @pytest.mark.asyncio
    async def test_call_tool_routing(self):
        from unittest.mock import AsyncMock, patch

        from memory_mcp.infrastructure.mcp_client.pool import MCPClientPool

        cfg = {"name": "myserver", "transport": "http", "url": "http://localhost:9999"}

        with patch("memory_mcp.infrastructure.mcp_client.http_client.call_tool", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"result": "ok"}
            async with MCPClientPool([cfg]) as pool:
                await pool.call_tool("myserver__do_thing", {"arg": "val"})
                mock_call.assert_called_once()
                call_args = mock_call.call_args
                assert call_args[0][1] == "do_thing"  # tool_name without prefix

    @pytest.mark.asyncio
    async def test_call_tool_invalid_name(self):
        from memory_mcp.infrastructure.mcp_client.pool import MCPClientPool

        async with MCPClientPool([]) as pool:
            result = await pool.call_tool("notqualified", {})
            assert "error" in result

    @pytest.mark.asyncio
    async def test_call_tool_unknown_server(self):
        from memory_mcp.infrastructure.mcp_client.pool import MCPClientPool

        async with MCPClientPool([]) as pool:
            result = await pool.call_tool("unknown__tool", {})
            assert "error" in result
