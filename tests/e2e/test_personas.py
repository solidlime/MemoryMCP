"""E2E tests for Personas tab (6-8).

ペルソナ管理 UI の基本描画と JS エラー不在を検証する。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.e2e
class TestPersonas:
    """Personas タブの UI 検証。"""

    @staticmethod
    def _open_personas(page):
        page.click('[data-tab="personas"]')
        page.wait_for_timeout(1500)

    def test_personas_panel_visible(self, page):
        """Personas タブクリックで #tab-personas パネルが表示される。"""
        self._open_personas(page)
        panel = page.locator("#tab-personas")
        assert panel.is_visible(), "#tab-personas should be visible"

    def test_personas_has_content(self, page):
        """Personas パネルにコンテンツがある。"""
        self._open_personas(page)
        content = page.locator("body").inner_text()
        assert len(content) > 50, "Personas tab should have content"

    def test_no_js_errors(self, page):
        """Personas タブロード時に JS エラーがない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        self._open_personas(page)
        assert errors == [], f"JS errors on Personas tab: {errors}"
