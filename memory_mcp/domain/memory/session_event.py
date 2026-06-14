from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionEvent:
    """Represents a recorded session event (tool call, chat message, etc.)."""

    session_id: str
    persona: str
    event_type: str  # 'tool_call', 'chat_message', 'llm_response', 'session_start', 'session_compact', 'generic'
    summary: str  # human-readable one-liner (e.g., "memory_create: パパが疲れている")
    timestamp: datetime = field(default_factory=datetime.now)
    detail: str | None = None  # optional longer detail
    metadata: dict[str, Any] | None = None  # optional JSON metadata
    id: int | None = None  # assigned by DB
