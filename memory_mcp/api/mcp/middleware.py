from __future__ import annotations

import contextvars
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

# Per-request persona resolved from HTTP headers.
_persona_var: contextvars.ContextVar[str] = contextvars.ContextVar("_persona_var", default="")


def _env_persona() -> str:
    """Resolve persona from environment variables."""
    return os.environ.get("PERSONA", os.environ.get("MEMORY_MCP_DEFAULT_PERSONA", "default"))


def resolve_persona_from_headers(
    authorization: str | None = None,
    x_persona: str | None = None,
) -> str:
    """Resolve persona from HTTP headers with environment fallback.

    Priority: Bearer token > X-Persona header > environment variable.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    if x_persona:
        stripped = x_persona.strip()
        if stripped:
            return stripped
    return _env_persona()


# Backward-compatible alias
def resolve_persona_from_token(authorization: str | None = None) -> str:
    """Resolve persona from Bearer token or environment."""
    return resolve_persona_from_headers(authorization=authorization)


def get_current_persona() -> str:
    """Get the persona for the current request.

    Returns the value set by :class:`PersonaMiddleware` (via *contextvars*),
    falling back to environment variables when running outside an HTTP
    request (e.g. stdio transport).
    """
    val = _persona_var.get()
    if val:
        return val
    return _env_persona()


class PersonaMiddleware:
    """ASGI middleware: extracts persona from HTTP headers into a contextvar.

    Priority: ``Authorization: Bearer <persona>`` >
              ``X-Persona: <persona>`` >
              environment variables ``PERSONA`` / ``MEMORY_MCP_DEFAULT_PERSONA``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            authorization: str | None = None
            x_persona: str | None = None

            for name, value in scope.get("headers", []):
                lower_name = name if isinstance(name, bytes) else name.encode()
                if lower_name == b"authorization":
                    authorization = value.decode("latin-1") if isinstance(value, bytes) else value
                elif lower_name == b"x-persona":
                    x_persona = value.decode("latin-1") if isinstance(value, bytes) else value

            persona = resolve_persona_from_headers(authorization, x_persona)
            token = _persona_var.set(persona)
            try:
                await self.app(scope, receive, send)
            finally:
                _persona_var.reset(token)
        else:
            await self.app(scope, receive, send)
