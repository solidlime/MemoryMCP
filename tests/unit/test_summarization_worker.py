"""Tests for SummarizationWorker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from memory_mcp.application.workers.summarization_worker import SummarizationWorker


def _make_settings(
    enabled: bool = True,
    interval_hours: float = 24.0,
    min_new_memories: int = 10,
) -> MagicMock:
    """テスト用 Settings を作成する。"""
    settings = MagicMock()
    settings.summarization.enabled = enabled
    settings.summarization.interval_hours = interval_hours
    settings.summarization.min_new_memories = min_new_memories
    return settings


def _make_ctx(total_count: int = 50, tag_dist: dict | None = None) -> MagicMock:
    """テスト用 AppContext を作成する。"""
    ctx = MagicMock()
    stats = {"total_count": total_count, "tag_distribution": tag_dist or {}}
    ctx.memory_service.get_stats.return_value = MagicMock(is_ok=True, value=stats)
    ctx.memory_service.create_memory.return_value = MagicMock(is_ok=True)
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
        """enabled=False の場合は start() してもスレッドが起動しない。"""
        settings = _make_settings(enabled=False)
        worker = SummarizationWorker(settings)
        worker.start()
        assert worker._running is False
        assert worker._thread is None

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
        settings = _make_settings()
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
        settings = _make_settings()
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
