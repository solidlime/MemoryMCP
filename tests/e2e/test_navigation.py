"""E2E tests for dashboard tab navigation.

6-1: Tab switching — タブボタンクリック・キーボードショートカット・
パネル排他表示・JSエラー不在を検証する。
"""

from __future__ import annotations

import pytest

# 全タブ定義（data-tab 属性値の順序）
ALL_TABS: list[str] = [
    "overview",
    "analytics",
    "memories",
    "graph",
    "import-export",
    "personas",
    "settings",
    "admin",
]

# キーボードショートカットとタブの対応（Alt+1 → overview, … Alt+8 → admin）
SHORTCUT_KEY_MAP: dict[str, str] = {str(i + 1): tab for i, tab in enumerate(ALL_TABS)}


@pytest.mark.e2e
class TestNavigation:
    """ダッシュボードのタブナビゲーション E2E テスト。"""

    # ------------------------------------------------------------------
    # 1. 初期読み込みで Overview タブが表示される
    # ------------------------------------------------------------------
    def test_initial_load_shows_overview(self, page):
        """ダッシュボード初期読み込みで Overview タブが表示される。"""
        # Overview タブボタンが active
        active_btn = page.locator("[data-tab='overview'].active")
        assert active_btn.count() == 1, "Overview tab button should be active on initial load"

        # Overview パネルが active
        active_panel = page.locator("#tab-overview.active")
        assert active_panel.count() == 1, "Overview panel should be visible on initial load"

    # ------------------------------------------------------------------
    # 2. 各タブボタンをクリックすると対応するパネルが表示される（8 タブ全て）
    # ------------------------------------------------------------------
    @pytest.mark.parametrize("tab", ALL_TABS)
    def test_click_each_tab(self, page, tab: str):
        """タブボタンをクリックすると対応するパネルが表示される。"""
        btn = page.locator(f"[data-tab='{tab}']")
        btn.click()
        page.wait_for_timeout(500)

        panel = page.locator(f"#tab-{tab}.active")
        assert panel.count() == 1, f"Panel for '{tab}' should become active after click"

    # ------------------------------------------------------------------
    # 3. クリックしたタブボタンに .active クラスが付く
    # ------------------------------------------------------------------
    @pytest.mark.parametrize("tab", ALL_TABS)
    def test_active_tab_button_highlighted(self, page, tab: str):
        """クリックしたタブボタンに .active クラスが付く。"""
        btn = page.locator(f"[data-tab='{tab}']")
        btn.click()
        page.wait_for_timeout(500)

        # クリックしたボタン自体が active を持つ
        active_btn = page.locator(f".tab-btn.active[data-tab='{tab}']")
        assert active_btn.count() == 1, f"Tab button '{tab}' should have .active class after click"

    # ------------------------------------------------------------------
    # 4. 常に 1 つのパネルだけが active である
    # ------------------------------------------------------------------
    @pytest.mark.parametrize("tab", ALL_TABS)
    def test_only_one_panel_visible(self, page, tab: str):
        """タブ切り替え後、active なパネルは常に 1 つだけ。"""
        page.locator(f"[data-tab='{tab}']").click()
        page.wait_for_timeout(500)

        active_panels = page.locator(".tab-panel.active")
        assert active_panels.count() == 1, (
            f"Exactly one panel should be active after switching to '{tab}', found {active_panels.count()}"
        )

    # ------------------------------------------------------------------
    # 5. キーボードショートカット（1-8）でタブ切り替え
    # ------------------------------------------------------------------
    @pytest.mark.parametrize(
        "key, expected_tab",
        list(SHORTCUT_KEY_MAP.items()),
        ids=[f"key-{k}->{v}" for k, v in SHORTCUT_KEY_MAP.items()],
    )
    def test_keyboard_shortcut_switches_tab(self, page, key: str, expected_tab: str):
        """キーボードの 1-8 でタブが切り替わる。"""
        page.keyboard.press(f"Alt+{key}")
        page.wait_for_timeout(500)

        # 期待するパネルが active
        panel = page.locator(f"#tab-{expected_tab}.active")
        assert panel.count() == 1, f"Alt+{key} should activate '{expected_tab}' panel"

        # 期待するボタンが active
        btn = page.locator(f".tab-btn.active[data-tab='{expected_tab}']")
        assert btn.count() == 1, f"Alt+{key} should highlight '{expected_tab}' tab button"

    # ------------------------------------------------------------------
    # 6. タブ切り替え時に JS エラーがない
    # ------------------------------------------------------------------
    def test_tab_switch_no_js_errors(self, page):
        """全タブを順に切り替えても JS エラーが発生しない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        for tab in ALL_TABS:
            page.locator(f"[data-tab='{tab}']").click()
            page.wait_for_timeout(500)

        assert errors == [], f"JS errors occurred during tab switching: {errors}"
