from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from memory_mcp.domain.memory.entities import Memory
    from memory_mcp.domain.shared.errors import SearchError
    from memory_mcp.domain.shared.result import Result


@runtime_checkable
class KeywordSearchStrategy(Protocol):
    """Strategy for keyword-based memory search."""

    def search(
        self, query: str, limit: int = 10
    ) -> Result[list[tuple[Memory, float]], SearchError]: ...


@runtime_checkable
class SemanticSearchStrategy(Protocol):
    """Strategy for semantic/vector-based memory search."""

    def search(
        self, query: str, limit: int = 10
    ) -> Result[list[tuple[Memory, float]], SearchError]: ...
