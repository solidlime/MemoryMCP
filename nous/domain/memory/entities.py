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
    source_context: str | None = None
    related_keys: list[str] = field(default_factory=list)
    summary_ref: str | None = None
    equipped_items: str | None = None
    access_count: int = 0
    last_accessed: datetime | None = None
    body_state: dict[str, float] | None = None
    state_snapped_at: datetime | None = None
    lifecycle_status: str = "active"


@dataclass
class MemoryStrength:
    """FSRS v6 power-law forgetting curve for a memory."""

    memory_key: str
    strength: float = 1.0
    stability: float = 1.0
    last_decay: datetime | None = None
    recall_count: int = 0
    last_recall: datetime | None = None

    def compute_recall(self, elapsed_hours: float, decay_exponent: float = 0.5) -> float:
        """R(t) = (1 + 19 * t_hours / (S * 24))^(-decay_exponent).

        Canonical FSRS v6 power-law decay. S = stability in days.
        At t = S*24h (one stability period), R = 20^(-0.5) ≈ 0.224.

        Args:
            elapsed_hours: Time since last decay in hours.
            decay_exponent: FSRS decay exponent (default 0.5 = canonical).
        """
        if self.stability <= 0:
            return 0.0
        return (1 + 19.0 * elapsed_hours / (self.stability * 24)) ** (-decay_exponent)

    def boost_on_recall(self) -> None:
        """Increase stability on successful recall."""
        self.recall_count += 1
        self.stability = min(self.stability * 1.5, 365.0)
        self.strength = 1.0
