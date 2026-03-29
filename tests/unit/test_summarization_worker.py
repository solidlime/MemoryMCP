"""Tests for SummarizationWorker."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from memory_mcp.application.workers.summarization_worker import SummarizationWorker
from memory_mcp.domain.memory.entities import Memory


def _make_settings(
    enabled: bool = True,
    extractive_enabled: bool = True,
    interval_hours: float = 24.0,
    min_new_memories: int = 10,
    min_importance: float = 0.3,
    max_memories_per_summary: int = 20,
) -> MagicMock:
    """テスト用 Settings を作成する。"""
    settings = MagicMock()
    settings.summarization.enabled = enabled
    settings.summarization.extractive_enabled = extractive_enabled
    settings.summarization.interval_hours = interval_hours
    settings.summarization.min_new_memories = min_new_memories
    settings.summarization.min_importance = min_importance
    settings.summarization.max_memories_per_summary = max_memories_per_summary
    return settings


def _make_ctx(total_count: int = 50, tag_dist: dict | None = None) -> MagicMock:
    """テスト用 AppContext を作成する。"""
    ctx = MagicMock()
    stats = {"total_count": total_count, "tag_distribution": tag_dist or {}}
    ctx.memory_service.get_stats.return_value = MagicMock(is_ok=True, value=stats)
    ctx.memory_service.create_memory.return_value = MagicMock(is_ok=True)
    return ctx


def _make_memory(
    key: str,
    content: str,
    importance: float = 0.2,
    tags: list[str] | None = None,
    days_old: float = 10.0,
) -> Memory:
    """テスト用 Memory エンティティを作成する。"""
    tz = ZoneInfo("Asia/Tokyo")
    now = datetime.now(tz)
    created = now - timedelta(days=days_old)
    return Memory(
        key=key,
        content=content,
        created_at=created,
        updated_at=created,
        importance=importance,
        tags=tags or [],
    )


def _make_extractive_ctx(memories: list) -> MagicMock:
    """抽出型要約テスト用 AppContext を作成する。"""
    ctx = MagicMock()
    ctx.memory_repo.find_all.return_value = MagicMock(is_ok=True, value=memories)
    ctx.memory_service.create_memory.return_value = MagicMock(is_ok=True)
    ctx.memory_service.delete_memory.return_value = MagicMock(is_ok=True)
    return ctx


class TestSummarizationWorkerStartStop:
    def test_start_enabled(self) -> None:
        """enabled=True の場合はスレッドが起動し _running=True になる。"""
        settings = _make_settings(enabled=True, interval_hours=9999)
        worker = SummarizationWorker(settings)
        worker.start()
        assert worker._running is True
        worker.stop()

    def test_start_disabled_skips(self) -> None:
        """enabled=False かつ extractive_enabled=False の場合は start() してもスレッドが起動しない。"""
        settings = _make_settings(enabled=False, extractive_enabled=False)
        worker = SummarizationWorker(settings)
        worker.start()
        assert worker._running is False
        assert worker._thread is None

    def test_start_extractive_only(self) -> None:
        """enabled=False でも extractive_enabled=True なら起動する。"""
        settings = _make_settings(enabled=False, extractive_enabled=True, interval_hours=9999)
        worker = SummarizationWorker(settings)
        worker.start()
        assert worker._running is True
        worker.stop()

    def test_stop(self) -> None:
        """stop() で _running が False になる。"""
        settings = _make_settings(interval_hours=9999)
        worker = SummarizationWorker(settings)
        worker.start()
        worker.stop()
        assert worker._running is False


class TestCreateStatisticalSummary:
    def test_creates_memory_with_summary_tags(self) -> None:
        """統計サマリーが ["summary", "daily_summary"] タグ付きで作成される。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx(total_count=30, tag_dist={"food": 5, "work": 3})

        worker._create_statistical_summary(ctx, "herta", new_count=15, stats=ctx.memory_service.get_stats().value)

        ctx.memory_service.create_memory.assert_called_once()
        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        assert call_kwargs["tags"] == ["summary", "daily_summary"]

    def test_creates_memory_with_correct_importance(self) -> None:
        """統計サマリーは importance=0.3 で作成される。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx()

        stats = {"total_count": 20, "tag_distribution": {}}
        worker._create_statistical_summary(ctx, "herta", new_count=5, stats=stats)

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        assert call_kwargs["importance"] == pytest.approx(0.3)

    def test_creates_memory_with_neutral_emotion(self) -> None:
        """統計サマリーは emotion=neutral で作成される。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx()

        stats = {"total_count": 20, "tag_distribution": {}}
        worker._create_statistical_summary(ctx, "herta", new_count=5, stats=stats)

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        assert call_kwargs["emotion"] == "neutral"

    def test_summary_content_includes_date_and_counts(self) -> None:
        """サマリー内容に日付・新規数・合計数が含まれる。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx(total_count=42)

        stats = {"total_count": 42, "tag_distribution": {}}
        worker._create_statistical_summary(ctx, "herta", new_count=12, stats=stats)

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        content: str = call_kwargs["content"]
        assert "Daily Summary" in content
        assert "12" in content
        assert "42" in content

    def test_summary_content_includes_top_tags(self) -> None:
        """サマリー内容にトップタグが含まれる。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx()

        stats = {"total_count": 10, "tag_distribution": {"milestone": 7, "bugfix": 3}}
        worker._create_statistical_summary(ctx, "herta", new_count=5, stats=stats)

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        content: str = call_kwargs["content"]
        assert "milestone" in content

    def test_summary_content_no_tags_shows_none(self) -> None:
        """タグが空のとき "none" と表示される。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx()

        stats = {"total_count": 5, "tag_distribution": {}}
        worker._create_statistical_summary(ctx, "herta", new_count=5, stats=stats)

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        content: str = call_kwargs["content"]
        assert "none" in content

    def test_create_memory_failure_does_not_raise(self) -> None:
        """create_memory が失敗しても例外を投げない。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx()
        ctx.memory_service.create_memory.return_value = MagicMock(is_ok=False, error="DB error")

        stats = {"total_count": 10, "tag_distribution": {}}
        # 例外が発生しないことを確認
        worker._create_statistical_summary(ctx, "herta", new_count=5, stats=stats)

    def test_source_context_is_worker_name(self) -> None:
        """source_context が summarization_worker になっている。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_ctx()

        stats = {"total_count": 10, "tag_distribution": {}}
        worker._create_statistical_summary(ctx, "herta", new_count=5, stats=stats)

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        assert call_kwargs["source_context"] == "summarization_worker"


class TestSummarizePersona:
    def test_skips_when_below_min_new_memories(self) -> None:
        """min_new_memories 未満の新規記憶ではサマリーを作成しない。"""
        settings = _make_settings(min_new_memories=10)
        worker = SummarizationWorker(settings)
        # 前回カウントを設定して差分を 5 (< 10) にする
        worker._last_counts["herta"] = 45
        ctx = _make_ctx(total_count=50)  # diff = 50 - 45 = 5

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_creates_summary_when_above_threshold(self) -> None:
        """min_new_memories 以上の新規記憶があればサマリーを作成する。"""
        settings = _make_settings(min_new_memories=10)
        worker = SummarizationWorker(settings)
        worker._last_counts["herta"] = 30
        ctx = _make_ctx(total_count=50)  # diff = 50 - 30 = 20 >= 10

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._summarize_persona("herta")

        ctx.memory_service.create_memory.assert_called_once()

    def test_updates_last_count_after_summary(self) -> None:
        """サマリー作成後に _last_counts が最新カウントで更新される。"""
        settings = _make_settings(min_new_memories=5)
        worker = SummarizationWorker(settings)
        worker._last_counts["herta"] = 0
        ctx = _make_ctx(total_count=20)  # diff = 20 >= 5

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._summarize_persona("herta")

        assert worker._last_counts["herta"] == 20

    def test_skips_entirely_new_persona_below_threshold(self) -> None:
        """初回実行（last_count=0）でも min_new_memories 未満ならスキップ。"""
        settings = _make_settings(min_new_memories=10)
        worker = SummarizationWorker(settings)
        ctx = _make_ctx(total_count=5)  # diff = 5 - 0 = 5 < 10

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_skips_when_get_stats_fails(self) -> None:
        """get_stats が失敗した場合はサマリーを作成しない。"""
        settings = _make_settings(min_new_memories=1)
        worker = SummarizationWorker(settings)
        ctx = MagicMock()
        ctx.memory_service.get_stats.return_value = MagicMock(is_ok=False, error="DB error")

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_handles_registry_get_exception(self) -> None:
        """AppContextRegistry.get() が例外を投げても処理が継続する。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.side_effect = KeyError("herta")
            # 例外が伝播しないことを確認
            worker._summarize_persona("herta")


class TestSummarizeAll:
    def test_summarizes_all_personas(self) -> None:
        """_summarize_all() が全ペルソナに対して _summarize_persona を呼ぶ。"""
        settings = _make_settings(enabled=True, extractive_enabled=False)
        worker = SummarizationWorker(settings)

        fake_contexts = {"alice": MagicMock(), "bob": MagicMock()}
        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry._contexts = fake_contexts
            with patch.object(worker, "_summarize_persona") as mock_summarize:
                worker._summarize_all()

        assert mock_summarize.call_count == 2
        called_personas = {call[0][0] for call in mock_summarize.call_args_list}
        assert called_personas == {"alice", "bob"}

    def test_continues_on_persona_error(self) -> None:
        """1ペルソナで例外が出ても残りのペルソナを処理する。"""
        settings = _make_settings(enabled=True, extractive_enabled=False)
        worker = SummarizationWorker(settings)

        fake_contexts = {"alice": MagicMock(), "bob": MagicMock()}
        call_order: list[str] = []

        def side_effect(persona: str) -> None:
            call_order.append(persona)
            if persona == "alice":
                raise RuntimeError("alice failed")

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry._contexts = fake_contexts
            with patch.object(worker, "_summarize_persona", side_effect=side_effect):
                worker._summarize_all()

        # alice がエラーでも bob は処理されている
        assert "bob" in call_order

    def test_handles_registry_exception(self) -> None:
        """AppContextRegistry._contexts.keys() が例外を投げても処理が終了しない。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry._contexts.keys.side_effect = RuntimeError("registry error")
            # 例外が伝播しないことを確認
            worker._summarize_all()

    def test_extractive_called_when_enabled(self) -> None:
        """extractive_enabled=True のとき _extractive_summarize_persona が呼ばれる。"""
        settings = _make_settings(enabled=False, extractive_enabled=True)
        worker = SummarizationWorker(settings)

        fake_contexts = {"alice": MagicMock()}
        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry._contexts = fake_contexts
            with patch.object(worker, "_extractive_summarize_persona") as mock_ext:
                worker._summarize_all()

        mock_ext.assert_called_once_with("alice")

    def test_statistical_not_called_when_disabled(self) -> None:
        """enabled=False のとき _summarize_persona は呼ばれない。"""
        settings = _make_settings(enabled=False, extractive_enabled=True)
        worker = SummarizationWorker(settings)

        fake_contexts = {"alice": MagicMock()}
        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry._contexts = fake_contexts
            with (
                patch.object(worker, "_summarize_persona") as mock_stat,
                patch.object(worker, "_extractive_summarize_persona"),
            ):
                worker._summarize_all()

        mock_stat.assert_not_called()


class TestExtractiveSummarizePersona:
    """抽出型要約ワーカーの単体テスト。"""

    def test_no_candidates_skips_create(self) -> None:
        """対象記憶がなければ create_memory は呼ばれない。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = _make_extractive_ctx([])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_creates_summary_for_old_low_importance_no_tags(self) -> None:
        """7日以上前・低重要度・タグなし → サマリーが作成される。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "テストコンテンツ", importance=0.1, days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.create_memory.assert_called_once()

    def test_skips_memories_with_tags(self) -> None:
        """タグ付き記憶は対象外。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "タグあり", importance=0.1, tags=["foo"], days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_skips_recent_memories(self) -> None:
        """7日以内の記憶は対象外。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "最近の記憶", importance=0.1, days_old=3)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_skips_high_importance_memories(self) -> None:
        """重要度 >= min_importance (0.3) の記憶は対象外。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "重要な記憶", importance=0.5, days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_skips_memory_at_importance_boundary(self) -> None:
        """重要度がちょうど min_importance (0.3) の場合も対象外。"""
        settings = _make_settings(min_importance=0.3)
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "境界値", importance=0.3, days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_summary_format(self) -> None:
        """サマリーの形式が '[要約] YYYY-MM-DD: ...' であること。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "これはテストコンテンツです", importance=0.1, days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        content: str = call_kwargs["content"]
        assert content.startswith("[要約]")
        assert "これはテストコンテンツ" in content

    def test_summary_tags_and_importance(self) -> None:
        """サマリーのタグが ['summary', 'auto']、重要度が 0.5。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "コンテンツ", importance=0.1, days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        assert call_kwargs["tags"] == ["summary", "auto"]
        assert call_kwargs["importance"] == pytest.approx(0.5)

    def test_source_context_is_extractive_worker(self) -> None:
        """source_context が extractive_summarization_worker になっている。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "コンテンツ", importance=0.1, days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        assert call_kwargs["source_context"] == "extractive_summarization_worker"

    def test_deletes_originals_after_summary(self) -> None:
        """サマリー作成後に元記憶を削除する。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem1 = _make_memory("k1", "記憶1", importance=0.1, days_old=10)
        mem2 = _make_memory("k2", "記憶2", importance=0.2, days_old=10)
        ctx = _make_extractive_ctx([mem1, mem2])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        assert ctx.memory_service.delete_memory.call_count == 2
        deleted_keys = {c[0][0] for c in ctx.memory_service.delete_memory.call_args_list}
        assert deleted_keys == {"k1", "k2"}

    def test_groups_by_date_creates_multiple_summaries(self) -> None:
        """異なる日付の記憶は別々にグループ化されサマリーが複数作成される。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem1 = _make_memory("k1", "8日前の記憶", importance=0.1, days_old=8)
        mem2 = _make_memory("k2", "15日前の記憶", importance=0.1, days_old=15)
        ctx = _make_extractive_ctx([mem1, mem2])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        # 2つの日付グループ → 2回 create_memory
        assert ctx.memory_service.create_memory.call_count == 2

    def test_same_day_memories_grouped_together(self) -> None:
        """同じ日付の記憶は1つのサマリーにまとめられる。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        # 同じ日（10日前）の2つの記憶
        mem1 = _make_memory("k1", "記憶A", importance=0.1, days_old=10)
        mem2 = _make_memory("k2", "記憶B", importance=0.1, days_old=10)
        ctx = _make_extractive_ctx([mem1, mem2])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        # 同じ日 → 1回 create_memory
        assert ctx.memory_service.create_memory.call_count == 1
        content = ctx.memory_service.create_memory.call_args[1]["content"]
        assert "記憶A" in content
        assert "記憶B" in content

    def test_content_truncated_to_50_chars(self) -> None:
        """各記憶のコンテンツは先頭50文字に切り詰められる。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        long_content = "あ" * 100
        mem = _make_memory("k1", long_content, importance=0.1, days_old=10)
        ctx = _make_extractive_ctx([mem])

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        call_kwargs = ctx.memory_service.create_memory.call_args[1]
        content: str = call_kwargs["content"]
        # プレフィックス "[要約] YYYY-MM-DD: " の後が最大50文字
        after_prefix = content.split(": ", 1)[1]
        assert len(after_prefix) <= 50

    def test_no_delete_if_summary_creation_fails(self) -> None:
        """サマリー作成失敗時は元記憶を削除しない。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        mem = _make_memory("k1", "記憶", importance=0.1, days_old=10)
        ctx = _make_extractive_ctx([mem])
        ctx.memory_service.create_memory.return_value = MagicMock(is_ok=False, error="DB error")

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.delete_memory.assert_not_called()

    def test_find_all_failure_skips(self) -> None:
        """find_all が失敗した場合はスキップする。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)
        ctx = MagicMock()
        ctx.memory_repo.find_all.return_value = MagicMock(is_ok=False)

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.return_value = ctx
            worker._extractive_summarize_persona("herta")

        ctx.memory_service.create_memory.assert_not_called()

    def test_registry_get_exception_handled(self) -> None:
        """AppContextRegistry.get() が例外を投げても処理が継続する。"""
        settings = _make_settings()
        worker = SummarizationWorker(settings)

        with patch("memory_mcp.application.use_cases.AppContextRegistry") as registry:
            registry.get.side_effect = KeyError("herta")
            # 例外が伝播しないことを確認
            worker._extractive_summarize_persona("herta")

