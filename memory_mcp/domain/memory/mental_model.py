"""MentalModel: Abstracted pattern derived from multiple related memories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MentalModel:
    """Abstracted pattern derived from multiple related memories."""

    content: str
    source_memory_keys: list[str] = field(default_factory=list)
    confidence: float = 0.7
    abstracted_at: datetime | None = None
    type_tag: str = ""  # the type tag that triggered this model
