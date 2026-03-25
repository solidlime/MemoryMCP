"""E2E tests for mobile responsive layout (6-9).

375x667 モバイルビューポートでのレンダリングと JS エラー不在を検証する。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestMobile:
    """モバイルレスポンシブ UI 検証。"""

    def test_mobile_renders(self, mobile_page):
        """モバイルビューポートでページが正常にレンダリングされる。"""
        assert mobile_page.locator("body").is_visible()
        content = mobile_page.locator("body").inner_text()
        assert len(content) > 0, "Mobile page should have content"

    def test_mobile_no_js_errors(self, mobile_page):
        """モバイルビューポートでリロードしても JS エラーがない。"""
        errors: list[str] = []
        mobile_page.on("pageerror", lambda err: errors.append(str(err)))
        mobile_page.reload()
        mobile_page.wait_for_load_state("networkidle", timeout=10000)
        assert errors == [], f"JS errors on mobile: {errors}"

    def test_mobile_body_not_overflowing(self, mobile_page):
        """モバイルで body の scroll width が viewport 幅を大幅に超えない。"""
        scroll_width = mobile_page.evaluate("document.body.scrollWidth")
        viewport_width = mobile_page.evaluate("window.innerWidth")
        # 横スクロールが発生していないこと（20px の余裕を許容）
        assert scroll_width <= viewport_width + 20, (
            f"Horizontal overflow detected: scrollWidth={scroll_width}, viewportWidth={viewport_width}"
        )
