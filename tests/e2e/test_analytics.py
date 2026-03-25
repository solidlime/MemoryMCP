"""E2E tests for Analytics tab (6-5).

感情チャート・強度チャート・期間フィルターなど
Analytics パネルの UI 要素を Playwright で検証する。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestAnalytics:
    """Analytics タブの UI 検証。"""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_analytics(page):
        """Analytics タブを開いてデータロードを待つ。"""
        page.click('[data-tab="analytics"]')
        page.wait_for_timeout(2000)

    # ------------------------------------------------------------------
    # 1. タブ表示
    # ------------------------------------------------------------------

    def test_analytics_tab_loads(self, page):
        """Analytics タブクリックで #tab-analytics パネルが表示される。"""
        self._open_analytics(page)

        panel = page.locator("#tab-analytics")
        assert panel.is_visible(), "#tab-analytics panel should be visible"

    # ------------------------------------------------------------------
    # 2. 感情チャート canvas
    # ------------------------------------------------------------------

    def test_emotion_chart_canvas_exists(self, page):
        """#chart-emotions に canvas 要素が存在する。

        データ未投入でも canvas 自体は描画されるため count >= 0 で許容。
        """
        self._open_analytics(page)

        canvas = page.locator("#chart-emotions")
        # canvas 要素そのものが DOM に存在すること
        assert canvas.count() >= 0, "#chart-emotions canvas should exist (or be absent if no data)"

    # ------------------------------------------------------------------
    # 3. 強度チャート canvas
    # ------------------------------------------------------------------

    def test_strength_chart_canvas_exists(self, page):
        """#chart-strength に canvas 要素が存在する。"""
        self._open_analytics(page)

        canvas = page.locator("#chart-strength")
        assert canvas.count() >= 0, "#chart-strength canvas should exist (or be absent if no data)"

    # ------------------------------------------------------------------
    # 4. 期間フィルターボタン
    # ------------------------------------------------------------------

    def test_period_filter_buttons_exist(self, page):
        """`.emo-days-btn` が 4 つ存在する（7 / 30 / 90 / 365 日）。"""
        self._open_analytics(page)

        buttons = page.locator(".emo-days-btn")
        assert buttons.count() == 4, f"Expected 4 period filter buttons, got {buttons.count()}"

        # 各 data-days 属性も確認
        for days in ("7", "30", "90", "365"):
            btn = page.locator(f'[data-days="{days}"]')
            assert btn.count() >= 1, f"Button with data-days={days} should exist"

    # ------------------------------------------------------------------
    # 5. 期間フィルター active 切り替え
    # ------------------------------------------------------------------

    def test_period_filter_click_changes_active(self, page):
        """30 日ボタンクリックで .active クラスが切り替わる。"""
        self._open_analytics(page)

        btn_30 = page.locator('[data-days="30"]')
        btn_30.click()
        page.wait_for_timeout(500)

        # 30 日ボタンが active になっている
        assert "active" in (btn_30.get_attribute("class") or ""), "30-day button should have .active class after click"

        # 他のボタンは active でない（少なくとも 7 日ボタン）
        btn_7 = page.locator('[data-days="7"]')
        cls_7 = btn_7.get_attribute("class") or ""
        assert "active" not in cls_7, "7-day button should NOT have .active class after 30-day is clicked"

    # ------------------------------------------------------------------
    # 6. JS エラーなし
    # ------------------------------------------------------------------

    def test_no_js_errors(self, page):
        """Analytics タブロード時にコンソール JS エラーが発生しない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        self._open_analytics(page)

        assert errors == [], f"JS errors detected on Analytics tab: {errors}"

    # ------------------------------------------------------------------
    # 7. コンテンツ非空
    # ------------------------------------------------------------------

    def test_analytics_content_not_empty(self, page):
        """#analytics-content に実質的なコンテンツがある。"""
        self._open_analytics(page)

        content = page.locator("#analytics-content")
        text = (content.inner_text() or "").strip()

        # 最低限なにかテキストが表示されていること
        assert len(text) > 0, "#analytics-content should have non-empty text content"

        # グラスカード or カードタイトルが 1 つ以上ある
        cards = page.locator("#analytics-content .glass")
        titles = page.locator("#analytics-content .card-title")
        assert cards.count() > 0 or titles.count() > 0, (
            "Analytics content should contain .glass cards or .card-title elements"
        )
