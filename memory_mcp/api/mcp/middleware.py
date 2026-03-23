from __future__ import annotations

import os


def resolve_persona_from_token(authorization: str | None = None) -> str:
    """Resolve persona from Bearer token or environment."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        return token
    return os.environ.get(
        "PERSONA", os.environ.get("MEMORY_MCP_DEFAULT_PERSONA", "default")
    )
