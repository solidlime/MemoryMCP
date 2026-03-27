from __future__ import annotations

import os
import re
from dataclasses import asdict
from typing import TYPE_CHECKING

from pydantic import BaseModel

from memory_mcp.application.use_cases import AppContextRegistry
from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)

_PERSONA_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class CreateMemoryRequest(BaseModel):
    content: str
    importance: float = 0.5
    emotion_type: str = "neutral"
    emotion_intensity: float = 0.0
    tags: list[str] | None = None
    privacy_level: str = "internal"
    source_context: str | None = None
    defer_vector: bool = False


class UpdateMemoryRequest(BaseModel):
    content: str | None = None
    importance: float | None = None
    emotion_type: str | None = None
    emotion_intensity: float | None = None
    tags: list[str] | None = None
    privacy_level: str | None = None


class UpdateContextRequest(BaseModel):
    emotion: str | None = None
    emotion_intensity: float | None = None
    physical_state: str | None = None
    mental_state: str | None = None
    environment: str | None = None
    relationship_status: str | None = None
    user_info: dict | None = None
    persona_info: dict | None = None
    fatigue: float | None = None
    warmth: float | None = None
    arousal: float | None = None
    speech_style: str | None = None


def _safe_get_context(persona: str):
    """Get AppContext for persona, returning None if init fails."""
    try:
        return AppContextRegistry.get(persona)
    except Exception as exc:
        logger.warning("Failed to get context for persona '%s': %s", persona, exc)
        return None


def _memory_to_dict(m) -> dict:
    """Convert a Memory dataclass to a JSON-safe dict."""
    d = asdict(m)
    for k in ("created_at", "updated_at", "last_accessed", "last_decay", "last_recall"):
        if k in d and d[k] is not None:
            d[k] = d[k].isoformat()
    if "emotion" in d:
        d["emotion_type"] = d.pop("emotion")
    return d


def _strength_to_dict(s) -> dict:
    """Convert a MemoryStrength dataclass to a JSON-safe dict."""
    d = asdict(s)
    for k in ("last_decay", "last_recall"):
        if k in d and d[k] is not None:
            d[k] = d[k].isoformat()
    return d


def _resolve_persona_from_request(request: Request, *, default: str | None = None) -> str:
    """Resolve persona from path params, HTTP headers, or environment.

    Priority: path parameter > Bearer token > X-Persona header > *default* > env var.
    """
    persona = request.path_params.get("persona")
    if persona:
        return persona

    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token and _PERSONA_PATTERN.match(token):
            return token

    x_persona = request.headers.get("x-persona")
    if x_persona:
        stripped = x_persona.strip()
        if stripped:
            return stripped

    if default is not None:
        return default
    return os.environ.get("PERSONA", os.environ.get("MEMORY_MCP_DEFAULT_PERSONA", "default"))
