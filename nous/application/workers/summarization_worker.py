"""Daily summarization worker for MemoryMCP.

Periodically checks all active personas for new memories and creates
summary records to help maintain long-term context coherence.

Three summarization paths:
1. **Statistical summary** — counts new memories, logs a daily stats entry.
2. **Extractive summary** — collapses old/low-importance/untagged memories
   into date-grouped plain-text entries (no LLM).
3. **LLM summary** — when ``use_llm=True`` and ``llm_api_key`` is set,
   each date group is sent to an OpenAI-compatible API for a structured
   Japanese summary; falls back to extractive on failure.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from nous.infrastructure.logging.structured import get_logger

if TYPE_CHECKING:
    from nous.config.settings import Settings

logger = get_logger(__name__)


class SummarizationWorker:
    """Background worker that summarizes memories once per day.

    Three summarization paths:
    - **Statistical summary** (``enabled=True``): counts new memories and
      logs a daily statistics entry.
    - **Extractive summary** (``extractive_enabled=True``, on by default):
      finds old (>7 days), low-importance (<min_importance), untagged memories,
      groups them by date, and collapses each group into a single readable
      summary entry without any LLM API call.
    - **LLM summary** (``use_llm=True`` + ``llm_api_key`` set): when the
      extractive-enabled path runs and LLM config is present, each date group
      is sent to an OpenAI-compatible API for a structured Japanese summary.
      Falls back to the extractive plain-text format on API failure.
    """

    SUMMARIZATION_SYSTEM_PROMPT = """あなたは日本語の長期記憶を整理する要約アシスタントです。

# 役割
複数の記憶エントリを1つの簡潔な要約メモリに統合する。

# 入力
- 同一日付の低重要度メモリ群（タグなし、古い記憶）
- それぞれ50文字程度のスニペット

# 出力規則
1. **日本語で出力**（固有名詞・専門用語は原文保持）
2. **200〜400文字**で簡潔に
3. 以下の構造で出力:
   - 冒頭に `[要約 YYYY-MM-DD]` プレフィックス
   - 主要トピックを `・` 箇条書きで2-5項目
   - 各項目は1文で要点を述べる
4. 事実のみ記載。推論・解釈は加えない
5. 個人名・場所・日時などの固有名詞は保持
6. 重複内容は1つにまとめる

# 出力例
[要約 2026-06-26]
・午前にコンビニで昼食（おにぎり2個、500円）を購入
・午後にプロジェクトのコードレビューを実施、3件の修正指摘
・夜に友人とカフェで30分会話、近況報告

# 禁止事項
- 絵文字・顔文字の使用
- 主観的評価（「良かった」「楽しかった」等）
- 未来への言及や予測
- 入力にない情報の追加
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
        from nous.application.use_cases import AppContextRegistry

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
        from nous.application.use_cases import AppContextRegistry

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

    def _call_llm_summarize(
        self,
        cfg: Any,  # SummarizationConfig
        snippets: list[str],
        date_str: str,
    ) -> str | None:
        """OpenAI互換API（OpenRouter経由）でLLM要約を生成。失敗時はNoneを返す。

        Args:
            cfg: SummarizationConfig (with llm_api_url, llm_api_key, llm_model, llm_max_tokens).
            snippets: List of memory content strings (already truncated to ~50 chars).
            date_str: "YYYY-MM-DD" date string for the group.

        Returns:
            Generated summary string, or None on failure.
        """
        import httpx  # noqa: PLC0415 — imported here only when LLM path is active

        user_prompt = f"# 日付\n{date_str}\n\n# 記憶スニペット\n"
        for i, s in enumerate(snippets, 1):
            user_prompt += f"{i}. {s}\n"

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{cfg.llm_api_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {cfg.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": cfg.llm_model,
                        "messages": [
                            {"role": "system", "content": self.SUMMARIZATION_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": cfg.llm_max_tokens,
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            content: str = data["choices"][0]["message"]["content"]
            if not content.strip():
                logger.warning("LLM summarization returned empty content for %s", date_str)
                return None
            return content.strip()
        except Exception:
            logger.exception("LLM summarization failed for %s", date_str)
            return None

    def _extractive_summarize_persona(self, persona: str) -> None:
        """7日以上前・低重要度・タグなし記憶を日付別にグループ化／要約。

        各グループを1つの要約記憶にまとめて元記憶を削除する。
        ``use_llm=True`` + ``llm_api_key`` が設定されていれば API（OpenAI互換）
        経由のLLM要約を試行し、失敗時は文字列連結による簡易要約にフォールバックする。
        """
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        from nous.application.use_cases import AppContextRegistry

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

            # LLMパス: use_llm=True かつ llm_api_key が設定済みなら API 要約
            if cfg.use_llm is True and isinstance(cfg.llm_api_key, str) and cfg.llm_api_key:
                llm_result = self._call_llm_summarize(cfg, [m.content[:50] for m in batch], date_str)
                # フォールバック: LLM失敗時は抽出型（文字列連結）
                summary_content = llm_result or f"[要約] {date_str}: {snippets}"
            else:
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
