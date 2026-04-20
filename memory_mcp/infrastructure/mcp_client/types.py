from __future__ import annotations

import json

from pydantic import BaseModel


class MCPServerConfig(BaseModel):
    name: str
    transport: str = "http"  # "http" | "stdio"
    url: str = ""
    command: str = ""
    args: list[str] = []
    headers: dict[str, str] = {}
    enabled: bool = True

    @classmethod
    def from_claude_entry(cls, name: str, entry: dict) -> MCPServerConfig:
        """Parse one mcpServers entry from Claude mcp.json format."""
        url = entry.get("url", "")
        command = entry.get("command", "")
        transport = "http" if url else "stdio"
        # env → headers (stdio convention), headers → headers (http convention)
        headers: dict[str, str] = {str(k): str(v) for k, v in (entry.get("headers") or entry.get("env") or {}).items()}
        return cls(
            name=name,
            transport=transport,
            url=url,
            command=command,
            args=list(entry.get("args") or []),
            headers=headers,
            enabled=True,
        )

    @classmethod
    def list_from_claude_config(cls, mcp_servers: dict) -> list[MCPServerConfig]:
        """Parse full mcpServers dict from Claude mcp.json."""
        return [cls.from_claude_entry(name, cfg) for name, cfg in (mcp_servers or {}).items()]

    def to_claude_entry(self) -> dict:
        """Convert to a single mcpServers entry (Claude mcp.json format)."""
        result: dict = {}
        if self.transport == "http":
            result["url"] = self.url
            if self.headers:
                result["headers"] = dict(self.headers)
        else:
            result["command"] = self.command
            if self.args:
                result["args"] = list(self.args)
            if self.headers:
                result["env"] = dict(self.headers)
        return result

    @staticmethod
    def to_claude_json(servers: list[MCPServerConfig]) -> str:
        """Serialize a list of configs as a mcp.json string."""
        mcp_servers = {srv.name: srv.to_claude_entry() for srv in servers}
        return json.dumps({"mcpServers": mcp_servers}, indent=2, ensure_ascii=False)


class MCPTool(BaseModel):
    name: str
    description: str = ""
    input_schema: dict = {}
    server_name: str = ""
    original_name: str = ""
