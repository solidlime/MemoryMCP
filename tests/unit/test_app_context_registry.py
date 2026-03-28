"""Unit tests for AppContextRegistry.get() - regression for UnboundLocalError."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from memory_mcp.application.use_cases import AppContextRegistry


@pytest.fixture(autouse=True)
def _reset_registry():
    """各テスト後に Registry の状態をリセットする。"""
    AppContextRegistry._contexts.clear()
    original_settings = AppContextRegistry._settings
    yield
    AppContextRegistry._contexts.clear()
    AppContextRegistry._settings = original_settings


def _mock_settings(forgetting_enabled: bool = False):
    s = MagicMock()
    s.forgetting.enabled = forgetting_enabled
    s.forgetting.decay_interval_seconds = 3600
    return s


class TestAppContextRegistry:
    def test_get_returns_context(self):
        """get() が AppContext を返す（UnboundLocalError が起きない）。"""
        settings = _mock_settings()
        AppContextRegistry.configure(settings)

        with patch("memory_mcp.application.use_cases.AppContext") as mock_app_ctx:
            mock_ctx = MagicMock()
            mock_app_ctx.return_value = mock_ctx
            result = AppContextRegistry.get("default")
            assert result is mock_ctx

    def test_get_same_persona_twice_no_error(self):
        """同一ペルソナで2回 get() しても UnboundLocalError が起きない。（回帰テスト）"""
        settings = _mock_settings()
        AppContextRegistry.configure(settings)

        with patch("memory_mcp.application.use_cases.AppContext") as mock_app_ctx:
            mock_ctx = MagicMock()
            mock_app_ctx.return_value = mock_ctx

            ctx1 = AppContextRegistry.get("alice")
            ctx2 = AppContextRegistry.get("alice")  # 2回目 - 以前はここで UnboundLocalError

            assert ctx1 is ctx2
            # AppContext は一度しか作られない
            assert mock_app_ctx.call_count == 1

    def test_get_different_personas_independent(self):
        """異なるペルソナは独立したコンテキストを持つ。"""
        settings = _mock_settings()
        AppContextRegistry.configure(settings)

        with patch("memory_mcp.application.use_cases.AppContext") as mock_app_ctx:
            ctx_a = MagicMock()
            ctx_b = MagicMock()
            mock_app_ctx.side_effect = [ctx_a, ctx_b]

            result_a = AppContextRegistry.get("alice")
            result_b = AppContextRegistry.get("bob")

            assert result_a is ctx_a
            assert result_b is ctx_b
            assert result_a is not result_b

    def test_decay_worker_started_only_on_first_get(self):
        """DecayWorker はペルソナ初回 get() のみ起動される（毎回起動しない）。"""
        settings = _mock_settings(forgetting_enabled=True)
        AppContextRegistry.configure(settings)

        with (
            patch("memory_mcp.application.use_cases.AppContext"),
            patch("memory_mcp.application.workers.decay_worker.DecayWorker") as mock_worker_cls,
        ):
            mock_worker = MagicMock()
            mock_worker_cls.return_value = mock_worker

            AppContextRegistry.get("alice")
            AppContextRegistry.get("alice")  # 2回目
            AppContextRegistry.get("alice")  # 3回目

            # 1回しか起動されていない
            assert mock_worker_cls.call_count == 1
            assert mock_worker.start.call_count == 1
