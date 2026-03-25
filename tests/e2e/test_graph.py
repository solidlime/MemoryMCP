"""E2E tests for Knowledge Graph tab (6-6).

グラフコンテナ・ノード制限・フィルター・物理演算トグルなど
Knowledge Graph パネルの UI 要素を Playwright で検証する。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestKnowledgeGraph:
    """Knowledge Graph タブの UI 検証。"""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_graph(page):
        """Graph タブを開いてグラフ描画を待つ。"""
        page.click('[data-tab="graph"]')
        page.wait_for_timeout(3000)

    # ------------------------------------------------------------------
    # 1. タブ表示
    # ------------------------------------------------------------------

    def test_graph_tab_loads(self, page):
        """Graph タブクリックで #tab-graph パネルが表示される。"""
        self._open_graph(page)

        panel = page.locator("#tab-graph")
        assert panel.is_visible(), "#tab-graph panel should be visible"

    # ------------------------------------------------------------------
    # 2. グラフコンテナ
    # ------------------------------------------------------------------

    def test_graph_container_exists(self, page):
        """#graph-container が DOM に存在する。"""
        self._open_graph(page)

        container = page.locator("#graph-container")
        assert container.count() >= 1, "#graph-container should exist in the DOM"

    # ------------------------------------------------------------------
    # 3. ノード制限ボタン
    # ------------------------------------------------------------------

    def test_graph_limit_buttons_exist(self, page):
        """ノード制限ボタン (.graph-limit-btn) が存在する。"""
        self._open_graph(page)

        buttons = page.locator(".graph-limit-btn")
        assert buttons.count() >= 1, "At least one .graph-limit-btn should exist"

        # 個別の data-limit 値も確認
        for limit in ("50", "100", "200"):
            btn = page.locator(f'[data-limit="{limit}"]')
            assert btn.count() >= 1, f"Button with data-limit={limit} should exist"

    # ------------------------------------------------------------------
    # 4. リフレッシュボタン
    # ------------------------------------------------------------------

    def test_graph_refresh_button_exists(self, page):
        """#graph-refresh-btn が存在する。"""
        self._open_graph(page)

        btn = page.locator("#graph-refresh-btn")
        assert btn.count() >= 1, "#graph-refresh-btn should exist"

    # ------------------------------------------------------------------
    # 5. 物理演算トグル
    # ------------------------------------------------------------------

    def test_graph_physics_toggle_exists(self, page):
        """#graph-physics-toggle が存在する。"""
        self._open_graph(page)

        toggle = page.locator("#graph-physics-toggle")
        assert toggle.count() >= 1, "#graph-physics-toggle should exist"

    # ------------------------------------------------------------------
    # 6. 統計表示
    # ------------------------------------------------------------------

    def test_graph_stats_visible(self, page):
        """#graph-stats が表示される。"""
        self._open_graph(page)

        stats = page.locator("#graph-stats")
        assert stats.count() >= 1, "#graph-stats element should exist"
        # 表示状態を確認（hidden でないこと）
        assert stats.first.is_visible(), "#graph-stats should be visible"

    # ------------------------------------------------------------------
    # 7. JS エラーなし
    # ------------------------------------------------------------------

    def test_no_js_errors(self, page):
        """Graph タブ操作中にコンソール JS エラーが発生しない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        self._open_graph(page)

        assert errors == [], f"JS errors detected on Graph tab: {errors}"
