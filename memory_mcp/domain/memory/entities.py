from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class Memory:
    """A single memory entry."""

    key: str
    content: str
    created_at: datetime
    updated_at: datetime
    importance: float = 0.5
    emotion: str = "neutral"
    emotion_intensity: float = 0.0
    tags: list[str] = field(default_factory=list)
    privacy_level: str = "internal"
    physical_state: str | None = None
    mental_state: str | None = None
    environment: str | None = None
    relationship_status: str | None = None
    action_tag: str | None = None
    source_context: str | None = None
    related_keys: list[str] = field(default_factory=list)
    summary_ref: str | None = None
    equipped_items: str | None = None
    access_count: int = 0
    last_accessed: datetime | None = None


@dataclass
class MemoryStrength:
    """Ebbinghaus forgetting curve strength for a memory."""

    memory_key: str
    strength: float = 1.0
    stability: float = 1.0
    last_decay: datetime | None = None
    recall_count: int = 0
    last_recall: datetime | None = None

    def compute_recall(self, elapsed_hours: float) -> float:
        """R(t) = e^(-t/S) where S = stability in days."""
        if self.stability <= 0:
            return 0.0
        return math.exp(-elapsed_hours / (self.stability * 24))

    def boost_on_recall(self) -> None:
        """Increase stability on successful recall."""
        self.recall_count += 1
        self.stability = min(self.stability * 1.5, 365.0)
        self.strength = 1.0
