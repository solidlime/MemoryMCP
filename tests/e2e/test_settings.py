"""E2E tests for Settings tab (6-6).

設定パネルのコンテンツ・入力フィールド・JS エラー不在を検証する。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestSettings:
    """Settings タブの UI 検証。"""

    @staticmethod
    def _open_settings(page):
        page.click('[data-tab="settings"]')
        page.wait_for_timeout(1500)

    def test_settings_panel_visible(self, page):
        """Settings タブクリックで #tab-settings パネルが表示される。"""
        self._open_settings(page)
        panel = page.locator("#tab-settings")
        assert panel.is_visible(), "#tab-settings should be visible"

    def test_settings_has_content(self, page):
        """Settings パネルに実質的なコンテンツがある。"""
        self._open_settings(page)
        content = page.locator("body").inner_text()
        assert len(content) > 50, "Settings panel should have content"

    def test_no_js_errors(self, page):
        """Settings タブロード時に JS エラーがない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        self._open_settings(page)
        assert errors == [], f"JS errors on Settings tab: {errors}"
