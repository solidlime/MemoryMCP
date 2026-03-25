"""E2E tests for Import/Export tab (6-7).

インポート・エクスポート UI の基本描画と JS エラー不在を検証する。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestImportExport:
    """Import/Export タブの UI 検証。"""

    @staticmethod
    def _open_import_export(page):
        page.click('[data-tab="import-export"]')
        page.wait_for_timeout(1500)

    def test_import_export_panel_visible(self, page):
        """Import/Export タブクリックで #tab-import-export パネルが表示される。"""
        self._open_import_export(page)
        panel = page.locator("#tab-import-export")
        assert panel.is_visible(), "#tab-import-export should be visible"

    def test_import_export_has_content(self, page):
        """Import/Export パネルにコンテンツがある。"""
        self._open_import_export(page)
        content = page.locator("body").inner_text()
        assert len(content) > 50, "Import/Export tab should have content"

    def test_no_js_errors(self, page):
        """Import/Export タブロード時に JS エラーがない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        self._open_import_export(page)
        assert errors == [], f"JS errors on Import/Export tab: {errors}"
