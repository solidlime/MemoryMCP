from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PersonaState:
    """Current persona state snapshot."""

    persona: str
    emotion: str = "neutral"
    emotion_intensity: float = 0.0
    physical_state: str | None = None
    mental_state: str | None = None
    environment: str | None = None
    relationship_status: str | None = None
    fatigue: float | None = None
    warmth: float | None = None
    arousal: float | None = None
    heart_rate: str | None = None
    touch_response: str | None = None
    action_tag: str | None = None
    user_info: dict = field(default_factory=dict)
    persona_info: dict = field(default_factory=dict)
    last_conversation_time: datetime | None = None


@dataclass
class ContextEntry:
    """Bi-temporal state entry."""

    persona: str
    key: str
    value: str
    valid_from: datetime
    valid_until: datetime | None = None
    change_source: str | None = None


@dataclass
class EmotionRecord:
    """Emotion history event."""

    id: int | None = None
    emotion_type: str = "neutral"
    intensity: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    trigger_memory_key: str | None = None
    context: str | None = None
