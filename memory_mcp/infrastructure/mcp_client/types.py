from __future__ import annotations

from pydantic import BaseModel


class MCPServerConfig(BaseModel):
    name: str
    transport: str = "http"  # "http" | "stdio"
    url: str = ""
    command: str = ""
    args: list[str] = []
    headers: dict[str, str] = {}
    enabled: bool = True


class MCPTool(BaseModel):
    name: str
    description: str = ""
    input_schema: dict = {}
    server_name: str = ""
    original_name: str = ""
