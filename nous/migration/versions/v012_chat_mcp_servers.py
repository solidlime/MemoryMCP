from __future__ import annotations

import contextlib


def upgrade(db) -> None:
    """Add MCP server config and tool result truncation settings to chat_settings."""
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN mcp_servers TEXT DEFAULT '[]'")
    with contextlib.suppress(Exception):
        db.execute("ALTER TABLE chat_settings ADD COLUMN tool_result_max_chars INTEGER DEFAULT 4000")
    db.commit()
