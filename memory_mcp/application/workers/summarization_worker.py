"""Daily summarization worker for MemoryMCP.

Periodically checks all active personas for new memories and creates
summary records to help maintain long-term context coherence.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from memory_mcp.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from memory_mcp.config.settings import Settings

logger = get_logger(__name__)


class SummarizationWorker:
    """Background worker that summarizes memories once per day.

    Runs two summarization paths:
    - Statistical summary (requires ``enabled=True``): counts new memories and
      logs a daily statistics entry.
    - Extractive summary (requires ``extractive_enabled=True``, on by default):
      finds old (>7 days), low-importance (<min_importance), untagged memories,
      groups them by date, and collapses each group into a single readable
      summary entry without any LLM API call.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize with Settings.

        Args:
            settings: Settings instance (with .summarization config)
        """
        self._settings = settings
        self._running = False
        self._thread: threading.Thread | None = None
        # Track memory counts per persona at last run: {persona: count}
        self._last_counts: dict[str, int] = {}

    def start(self) -> None:
        """Start the background summarization thread."""
        cfg = self._settings.summarization
        if not cfg.enabled and not cfg.extractive_enabled:
            logger.info("SummarizationWorker: disabled by config, skipping start")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            "SummarizationWorker started (interval=%.1fh, min_new=%d, extractive=%s)",
            cfg.interval_hours,
            cfg.min_new_memories,
            cfg.extractive_enabled,
        )

    def stop(self) -> None:
        """Stop the background thread."""
        self._running = False
        logger.info("SummarizationWorker stopped")

    def _run(self) -> None:
        """Main loop: sleep then summarize."""
        interval_seconds = self._settings.summarization.interval_hours * 3600
        while self._running:
            time.sleep(interval_seconds)
            if self._running:
                self._summarize_all()

    def _summarize_all(self) -> None:
        """Summarize memories for all active personas."""
        from memory_mcp.application.use_cases import AppContextRegistry

        try:
            personas = list(AppContextRegistry._contexts.keys())
        except Exception:
            logger.exception("SummarizationWorker: failed to list personas")
            return

        cfg = self._settings.summarization
        for persona in personas:
            if cfg.enabled:
                try:
                    self._summarize_persona(persona)
                except Exception:
                    logger.exception("SummarizationWorker: error summarizing persona=%s", persona)
            if cfg.extractive_enabled:
                try:
                    self._extractive_summarize_persona(persona)
                except Exception:
                    logger.exception("SummarizationWorker: error in extractive summarization for persona=%s", persona)

    def _summarize_persona(self, persona: str) -> None:
        """Summarize memories for a single persona if new memories exist."""
        from memory_mcp.application.use_cases import AppContextRegistry

        try:
            ctx = AppContextRegistry.get(persona)
        except Exception:
            logger.debug("SummarizationWorker: could not get context for %s", persona)
            return

        # Get current memory count via MemoryService
        stats_result = ctx.memory_service.get_stats()
        if not stats_result.is_ok:
            return
        current_count: int = stats_result.value.get("total_count", 0)

        # Skip if not enough new memories since last run
        last_count = self._last_counts.get(persona, 0)
        min_new = self._settings.summarization.min_new_memories
        new_count = current_count - last_count
        if new_count < min_new:
            logger.debug(
                "SummarizationWorker: skipping %s (count=%d, last=%d, min_new=%d)",
                persona,
                current_count,
                last_count,
                min_new,
            )
            return

        logger.info(
            "SummarizationWorker: summarizing %s (%d new memories)",
            persona,
            new_count,
        )

        self._create_statistical_summary(ctx, persona, new_count, stats_result.value)

        # Update last count only on success
        self._last_counts[persona] = current_count

    def _create_statistical_summary(
        self,
        ctx: object,
        persona: str,
        new_count: int,
        stats: dict,
    ) -> None:
        """Create a simple statistical summary memory entry."""
        now = datetime.now(UTC)
        date_str = now.strftime("%Y-%m-%d")

        total: int = stats.get("total_count", 0)
        tag_dist: dict = stats.get("tag_distribution", {})
        top_tags = sorted(tag_dist.items(), key=lambda x: x[1], reverse=True)[:5]
        top_tags_str = ", ".join(f"{t}({c})" for t, c in top_tags) if top_tags else "none"

        summary_content = (
            f"[Daily Summary {date_str}] "
            f"{new_count} new memories recorded. "
            f"Total memories: {total}. "
            f"Top topics: {top_tags_str}."
        )

        try:
            result = ctx.memory_service.create_memory(  # type: ignore[union-attr]
                content=summary_content,
                importance=0.3,
                emotion="neutral",
                emotion_intensity=0.3,
                tags=["summary", "daily_summary"],
                privacy_level="private",
                source_context="summarization_worker",
            )
            if result.is_ok:
                logger.info("SummarizationWorker: created summary for %s", persona)
            else:
                logger.warning(
                    "SummarizationWorker: failed to create summary for %s: %s",
                    persona,
                    result.error,
                )
        except Exception:
            logger.exception("SummarizationWorker: error creating summary for %s", persona)

    def _extractive_summarize_persona(self, persona: str) -> None:
        """LLM不要な抽出型要約ワーカー。

        7日以上前・低重要度（< min_importance）・タグなしの記憶を日付別にグループ化し、
        各グループを1つの要約記憶にまとめて元記憶を削除する。
        """
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        from memory_mcp.application.use_cases import AppContextRegistry

        try:
            ctx = AppContextRegistry.get(persona)
        except Exception:
            logger.debug("SummarizationWorker: could not get context for extractive %s", persona)
            return

        all_result = ctx.memory_repo.find_all()  # type: ignore[union-attr]
        if not all_result.is_ok:
            return

        cfg = self._settings.summarization
        tz = ZoneInfo("Asia/Tokyo")
        now = datetime.now(tz)
        cutoff = now - timedelta(days=7)

        def _aware(dt: datetime) -> datetime:
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=tz)

        # Filter: >7 days old + importance < min_importance + no tags
        candidates = [
            m
            for m in all_result.value
            if not m.tags and m.importance < cfg.min_importance and _aware(m.created_at) < cutoff
        ]

        if not candidates:
            logger.debug("SummarizationWorker: no extractive candidates for %s", persona)
            return

        # Group by calendar date of created_at
        groups: dict[str, list] = {}
        for m in candidates:
            date_str = _aware(m.created_at).strftime("%Y-%m-%d")
            groups.setdefault(date_str, []).append(m)

        summarized_count = 0
        deleted_count = 0
        for date_str, memories in sorted(groups.items()):
            batch = memories[: cfg.max_memories_per_summary]
            snippets = "; ".join(m.content[:50] for m in batch)
            summary_content = f"[要約] {date_str}: {snippets}"

            result = ctx.memory_service.create_memory(  # type: ignore[union-attr]
                content=summary_content,
                importance=0.5,
                emotion="neutral",
                emotion_intensity=0.3,
                tags=["summary", "auto"],
                privacy_level="private",
                source_context="extractive_summarization_worker",
            )

            if result.is_ok:
                summarized_count += 1
                for m in batch:
                    del_result = ctx.memory_service.delete_memory(m.key)  # type: ignore[union-attr]
                    if del_result.is_ok:
                        deleted_count += 1
            else:
                logger.warning(
                    "SummarizationWorker: extractive summary creation failed for %s on %s: %s",
                    persona,
                    date_str,
                    result.error,
                )

        logger.info(
            "SummarizationWorker: extractive summary for %s: %d groups created, %d memories deleted",
            persona,
            summarized_count,
            deleted_count,
        )
