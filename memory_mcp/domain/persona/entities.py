from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# fmt: off
BASIC_EMOTIONS: list[str] = [
    "joy", "sadness", "anger", "fear", "disgust",
    "surprise", "love", "trust", "anticipation",
]
# fmt: on


def default_emotions() -> dict[str, float]:
    """Return a dict with all basic emotions set to 0.0."""
    return {e: 0.0 for e in BASIC_EMOTIONS}


def compute_dominant_emotion(emotions: dict[str, float]) -> tuple[str, float]:
    """Return (dominant_emotion_name, intensity) from an emotions dict.
    Returns ('neutral', 0.0) for empty or all-zero dicts."""
    if not emotions:
        return ("neutral", 0.0)
    dominant = max(emotions.items(), key=lambda kv: kv[1])
    if dominant[1] <= 0.0:
        return ("neutral", 0.0)
    return dominant


@dataclass
class PersonaState:
    """Current persona state snapshot."""

    persona: str
    emotion: str = "neutral"
    emotion_intensity: float = 0.0
    emotions: dict[str, float] = field(default_factory=default_emotions)
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
    speech_style: str | None = None
    user_info: dict = field(default_factory=dict)
    persona_info: dict = field(default_factory=dict)
    last_conversation_time: datetime | None = None

    @property
    def dominant_emotion(self) -> str:
        """Return the dominant (highest-intensity) emotion name."""
        if not self.emotions:
            return self.emotion or "neutral"
        dominant, _ = compute_dominant_emotion(self.emotions)
        return dominant

    @property
    def dominant_intensity(self) -> float:
        """Return the intensity of the dominant emotion."""
        if not self.emotions:
            return self.emotion_intensity or 0.0
        _, intensity = compute_dominant_emotion(self.emotions)
        return intensity


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
    emotions: dict[str, float] | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    trigger_memory_key: str | None = None
    context: str | None = None
