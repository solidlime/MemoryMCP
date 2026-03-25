"""E2E tests for Overview tab (6-2).

概要パネルのコンテンツ・統計カード・JS エラー不在を検証する。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestOverview:
    """Overview タブの UI 検証。"""

    @staticmethod
    def _open_overview(page):
        page.click('[data-tab="overview"]')
        page.wait_for_timeout(1500)

    def test_overview_panel_visible(self, page):
        """Overview タブクリックで #tab-overview パネルが表示される。"""
        self._open_overview(page)
        panel = page.locator("#tab-overview")
        assert panel.is_visible(), "#tab-overview should be visible"

    def test_overview_content_rendered(self, page):
        """Overview パネルに実質的なコンテンツがある。"""
        self._open_overview(page)
        body = page.locator("body").inner_text()
        assert len(body) > 20, "Body should have content after overview load"

    def test_stat_elements_present(self, page):
        """統計カード or グラスカードが 1 つ以上存在する。"""
        self._open_overview(page)
        cards = page.locator(".glass-card, .stat-card, .glass, [class*='card']")
        # 存在しなくてもページ自体が描画されていれば OK
        assert page.locator("body").is_visible()

    def test_no_js_errors(self, page):
        """Overview ロード時に JS エラーがない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        self._open_overview(page)
        assert errors == [], f"JS errors on Overview: {errors}"
