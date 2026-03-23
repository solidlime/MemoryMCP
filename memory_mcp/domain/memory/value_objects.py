from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_EMOTIONS: list[str] = [
    "neutral", "joy", "sadness", "anger", "fear", "surprise",
    "disgust", "trust", "anticipation", "love", "nostalgia",
    "curiosity", "pride", "shame", "guilt", "envy", "gratitude",
    "awe", "contempt", "anxiety", "excitement", "calm",
]

ALLOWED_PRIVACY_LEVELS: list[str] = ["internal", "shared", "secret"]

_KEY_PATTERN = re.compile(r"^[a-z_]+_\d{14}$")


@dataclass(frozen=True, slots=True)
class MemoryKey:
    """Validated memory key in format {prefix}_YYYYMMDDHHMMSS."""

    value: str

    def __post_init__(self) -> None:
        if not _KEY_PATTERN.match(self.value):
            raise ValueError(
                f"Invalid memory key format: {self.value!r}. "
                f"Expected {{prefix}}_YYYYMMDDHHMMSS"
            )


@dataclass(frozen=True, slots=True)
class Importance:
    """Importance score clamped to [0.0, 1.0]."""

    value: float

    def __post_init__(self) -> None:
        clamped = max(0.0, min(1.0, self.value))
        if clamped != self.value:
            object.__setattr__(self, "value", clamped)


@dataclass(frozen=True, slots=True)
class Emotion:
    """Validated emotion type."""

    value: str

    def __post_init__(self) -> None:
        if self.value not in ALLOWED_EMOTIONS:
            raise ValueError(
                f"Invalid emotion: {self.value!r}. "
                f"Allowed: {ALLOWED_EMOTIONS}"
            )


@dataclass(frozen=True, slots=True)
class PrivacyLevel:
    """Validated privacy level."""

    value: str

    def __post_init__(self) -> None:
        if self.value not in ALLOWED_PRIVACY_LEVELS:
            raise ValueError(
                f"Invalid privacy level: {self.value!r}. "
                f"Allowed: {ALLOWED_PRIVACY_LEVELS}"
            )
