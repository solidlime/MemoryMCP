"""ToolRegistry: built-in/MCPツールの統一管理。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.application.chat.tools.builtin import execute_tool, filter_extra_tools, truncate_tool_result
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext
    from memory_mcp.domain.chat_config import ChatConfig
    from memory_mcp.infrastructure.llm.base import ToolDefinition
    from memory_mcp.infrastructure.mcp_client import MCPClientPool

logger = get_logger(__name__)


class ToolRegistry:
    """built-in + MCP ツールを統一管理し、重複を除去して提供する。"""

    def __init__(
        self,
        builtin_tools: list[ToolDefinition],
        mcp_pool: MCPClientPool | None = None,
    ) -> None:
        extra = mcp_pool.list_all_tools() if mcp_pool else []
        filtered_extra = filter_extra_tools(extra)
        # builtin が優先: 同名の MCP ツールは除外
        builtin_names = {t.name for t in builtin_tools}
        self._builtin = list(builtin_tools)
        self._extra = [t for t in filtered_extra if t.name not in builtin_names]
        self._mcp_pool = mcp_pool

    def get_all_tools(self) -> list[ToolDefinition]:
        """重複除去済みの全ツールリストを返す。"""
        return self._builtin + self._extra

    def is_mcp_tool(self, tool_name: str) -> bool:
        """MCPプール経由で呼ぶべきツールか判定する。"""
        return "__" in tool_name

    async def execute(
        self,
        ctx: AppContext,
        config: ChatConfig,
        tool_name: str,
        tool_input: dict,
    ) -> dict:
        """ツール名に応じて built-in / MCP を自動ルーティングして実行する。"""
        try:
            if self.is_mcp_tool(tool_name):
                if self._mcp_pool is None:
                    return {"status": "error", "message": "MCP pool not available"}
                return await self._mcp_pool.call_tool(tool_name, tool_input)
            return await execute_tool(ctx, config, tool_name, tool_input)
        except Exception as e:
            logger.exception("ToolRegistry.execute failed: %s", tool_name)
            return {"status": "error", "message": str(e)}

    def truncate_result(self, result: dict, max_chars: int) -> dict:
        return truncate_tool_result(result, max_chars)
