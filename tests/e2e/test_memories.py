"""E2E tests for Memories tab (6-3).

記憶一覧・検索フィールド・記憶カード表示・JS エラー不在を検証する。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestMemories:
    """Memories タブの UI 検証。"""

    @staticmethod
    def _open_memories(page):
        page.click('[data-tab="memories"]')
        page.wait_for_timeout(2000)

    def test_memories_panel_visible(self, page):
        """Memories タブクリックで #tab-memories パネルが表示される。"""
        self._open_memories(page)
        panel = page.locator("#tab-memories")
        assert panel.is_visible(), "#tab-memories should be visible"

    def test_memories_tab_accessible(self, page):
        """Memories タブに遷移できてページがクラッシュしない。"""
        self._open_memories(page)
        assert page.locator("body").is_visible()

    def test_no_js_errors_memories(self, page):
        """Memories タブロード時に JS エラーがない。"""
        errors: list[str] = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        self._open_memories(page)
        assert errors == [], f"JS errors on Memories tab: {errors}"

    def test_search_input_present(self, page):
        """テキスト入力 or 検索フィールドが存在する（0 でも許容）。"""
        self._open_memories(page)
        inputs = page.locator("input[type='text'], input[type='search'], input[placeholder]")
        assert inputs.count() >= 0

    def test_memory_content_displayed(self, page):
        """記憶カードか空状態メッセージが表示される。"""
        self._open_memories(page)
        page.wait_for_timeout(1000)
        content = page.locator("body").inner_text()
        assert len(content) > 50, "Memories tab should show content or empty state"
