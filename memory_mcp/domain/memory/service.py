from __future__ import annotations

from typing import TYPE_CHECKING

from memory_mcp.domain.memory.entities import Memory, MemoryStrength
from memory_mcp.domain.shared.errors import (
    DomainError,
    MemoryNotFoundError,
    MemoryValidationError,
)
from memory_mcp.domain.shared.result import Failure, Result, Success
from memory_mcp.domain.shared.time_utils import generate_memory_key, get_now

if TYPE_CHECKING:
    from memory_mcp.domain.memory.repository import MemoryRepository


class MemoryService:
    """Domain service for memory operations."""

    def __init__(
        self,
        repo: MemoryRepository,
        entity_service: object | None = None,
    ) -> None:
        self._repo = repo
        self._entity_service = entity_service

    def create_memory(
        self,
        content: str,
        importance: float = 0.5,
        emotion: str = "neutral",
        emotion_intensity: float = 0.0,
        tags: list[str] | None = None,
        privacy_level: str = "internal",
        source_context: str | None = None,
        **extra_fields: object,
    ) -> Result[Memory, DomainError]:
        """Create and persist a new memory entry."""
        if not content or not content.strip():
            return Failure(MemoryValidationError("Content must not be empty"))

        now = get_now()
        key = generate_memory_key()
        memory = Memory(
            key=key,
            content=content.strip(),
            created_at=now,
            updated_at=now,
            importance=max(0.0, min(1.0, importance)),
            emotion=emotion,
            emotion_intensity=max(0.0, min(1.0, emotion_intensity)),
            tags=tags or [],
            privacy_level=privacy_level,
            source_context=source_context,
            **{k: v for k, v in extra_fields.items() if hasattr(Memory, k)},
        )
        result = self._repo.save(memory)
        if not result.is_ok:
            return Failure(result.error)

        # Record version 1
        self._repo.save_version(
            memory_key=key,
            version=1,
            content=memory.content,
            metadata=None,
            changed_by="user",
            change_type="create",
        )

        # Entity extraction hook (best-effort, never blocks create)
        if self._entity_service is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._entity_service.extract_and_link(
                    memory_key=key,
                    content=content.strip(),
                    tags=tags,
                )

        return Success(memory)

    def get_memory(self, key: str) -> Result[Memory, DomainError]:
        """Retrieve a memory by key."""
        result = self._repo.find_by_key(key)
        if not result.is_ok:
            return Failure(result.error)
        if result.value is None:
            return Failure(MemoryNotFoundError(f"Memory not found: {key}"))
        return Success(result.value)

    def update_memory(self, key: str, **updates: object) -> Result[Memory, DomainError]:
        """Update fields of an existing memory."""
        existing = self._repo.find_by_key(key)
        if not existing.is_ok:
            return Failure(existing.error)
        if existing.value is None:
            return Failure(MemoryNotFoundError(f"Memory not found: {key}"))

        # Capture pre-update snapshot for versioning
        old_memory = existing.value
        snapshot = {
            "content": old_memory.content,
            "importance": old_memory.importance,
            "emotion": old_memory.emotion,
            "tags": old_memory.tags,
            "privacy_level": old_memory.privacy_level,
        }

        updates["updated_at"] = get_now()
        result = self._repo.update(key, **updates)
        if not result.is_ok:
            return Failure(result.error)

        # Record new version
        ver_result = self._repo.get_latest_version_number(key)
        next_ver = (ver_result.value + 1) if ver_result.is_ok else 1
        self._repo.save_version(
            memory_key=key,
            version=next_ver,
            content=str(updates.get("content", old_memory.content)),
            metadata=snapshot,
            changed_by="user",
            change_type="update",
        )

        return Success(result.value)

    def delete_memory(self, key: str) -> Result[None, DomainError]:
        """Delete a memory by key."""
        existing = self._repo.find_by_key(key)
        if not existing.is_ok:
            return Failure(existing.error)
        if existing.value is None:
            return Failure(MemoryNotFoundError(f"Memory not found: {key}"))

        # Record delete version
        old_memory = existing.value
        ver_result = self._repo.get_latest_version_number(key)
        next_ver = (ver_result.value + 1) if ver_result.is_ok else 1
        snapshot = {
            "content": old_memory.content,
            "importance": old_memory.importance,
            "emotion": old_memory.emotion,
            "tags": old_memory.tags,
        }
        self._repo.save_version(
            memory_key=key,
            version=next_ver,
            content=old_memory.content,
            metadata=snapshot,
            changed_by="user",
            change_type="delete",
        )

        return self._repo.delete(key)

    def get_recent(self, limit: int = 10) -> Result[list[Memory], DomainError]:
        """Get most recent memories."""
        return self._repo.find_recent(limit)

    def get_stats(self) -> Result[dict, DomainError]:
        """Get memory statistics."""
        count_result = self._repo.count()
        if not count_result.is_ok:
            return Failure(count_result.error)

        all_result = self._repo.find_all()
        if not all_result.is_ok:
            return Failure(all_result.error)

        memories = all_result.value
        tag_dist: dict[str, int] = {}
        emotion_dist: dict[str, int] = {}
        for m in memories:
            for tag in m.tags:
                tag_dist[tag] = tag_dist.get(tag, 0) + 1
            emotion_dist[m.emotion] = emotion_dist.get(m.emotion, 0) + 1

        return Success(
            {
                "total_count": count_result.value,
                "tag_distribution": tag_dist,
                "emotion_distribution": emotion_dist,
            }
        )

    def boost_recall(self, key: str) -> Result[MemoryStrength, DomainError]:
        """Boost memory strength on recall."""
        strength_result = self._repo.get_strength(key)
        if not strength_result.is_ok:
            return Failure(strength_result.error)

        strength = strength_result.value
        if strength is None:
            strength = MemoryStrength(memory_key=key)

        strength.boost_on_recall()
        strength.last_recall = get_now()

        save_result = self._repo.save_strength(strength)
        if not save_result.is_ok:
            return Failure(save_result.error)
        return Success(strength)

    # --- Core Memory (Memory Blocks) ---

    def write_block(
        self,
        block_name: str,
        content: str,
        **opts: object,
    ) -> Result[None, DomainError]:
        """Write a named memory block."""
        if not block_name or not block_name.strip():
            return Failure(MemoryValidationError("Block name must not be empty"))
        if not content:
            return Failure(MemoryValidationError("Block content must not be empty"))
        return self._repo.save_block(
            block_name=block_name.strip(),
            content=content,
            block_type=str(opts.get("block_type", "custom")),
            max_tokens=int(opts.get("max_tokens", 500)),
            priority=int(opts.get("priority", 0)),
            metadata=opts.get("metadata") if isinstance(opts.get("metadata"), dict) else None,
        )

    def read_block(self, block_name: str) -> Result[dict | None, DomainError]:
        """Read a named memory block."""
        return self._repo.get_block(block_name)

    def list_blocks(self) -> Result[list[dict], DomainError]:
        """List all memory blocks."""
        return self._repo.list_blocks()

    def get_memory_history(self, key: str) -> Result[list[dict], DomainError]:
        """Get version history for a memory."""
        return self._repo.get_versions(key)

    def delete_block(self, block_name: str) -> Result[None, DomainError]:
        """Delete a named memory block."""
        return self._repo.delete_block(block_name)
