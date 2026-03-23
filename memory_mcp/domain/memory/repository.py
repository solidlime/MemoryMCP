from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from memory_mcp.domain.memory.entities import Memory, MemoryStrength
    from memory_mcp.domain.shared.errors import RepositoryError
    from memory_mcp.domain.shared.result import Result


@runtime_checkable
class MemoryRepository(Protocol):
    """Repository interface for memory persistence."""

    def save(self, memory: Memory) -> Result[str, RepositoryError]: ...

    def find_by_key(self, key: str) -> Result[Memory | None, RepositoryError]: ...

    def find_recent(self, limit: int = 10) -> Result[list[Memory], RepositoryError]: ...

    def find_by_tags(
        self, tags: list[str], limit: int = 10
    ) -> Result[list[Memory], RepositoryError]: ...

    def update(self, key: str, **kwargs: Any) -> Result[Memory, RepositoryError]: ...

    def delete(self, key: str) -> Result[None, RepositoryError]: ...

    def count(self) -> Result[int, RepositoryError]: ...

    def search_keyword(
        self, query: str, limit: int = 10
    ) -> Result[list[tuple[Memory, float]], RepositoryError]: ...

    def find_all(self) -> Result[list[Memory], RepositoryError]: ...

    # Memory strength
    def get_strength(
        self, key: str
    ) -> Result[MemoryStrength | None, RepositoryError]: ...

    def save_strength(
        self, strength: MemoryStrength
    ) -> Result[None, RepositoryError]: ...

    def get_all_strengths(
        self,
    ) -> Result[list[MemoryStrength], RepositoryError]: ...

    # Memory blocks (Core Memory)
    def get_block(
        self, block_name: str
    ) -> Result[dict | None, RepositoryError]: ...

    def save_block(
        self,
        block_name: str,
        content: str,
        block_type: str = "custom",
        max_tokens: int = 500,
        priority: int = 0,
        metadata: dict | None = None,
    ) -> Result[None, RepositoryError]: ...

    def list_blocks(self) -> Result[list[dict], RepositoryError]: ...

    def delete_block(self, block_name: str) -> Result[None, RepositoryError]: ...

    # Memory versions
    def save_version(
        self,
        memory_key: str,
        version: int,
        content: str,
        metadata: dict | None,
        changed_by: str,
        change_type: str,
    ) -> Result[None, RepositoryError]: ...

    def get_versions(self, memory_key: str) -> Result[list[dict], RepositoryError]: ...

    def get_version(
        self, memory_key: str, version: int
    ) -> Result[dict | None, RepositoryError]: ...

    def get_latest_version_number(self, memory_key: str) -> Result[int, RepositoryError]: ...
