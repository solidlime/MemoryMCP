"""Regression tests for chat tab control wiring."""

from memory_mcp.api.http.sections.chat import render_chat_js, render_chat_tab


def test_chat_tab_buttons_use_panel_toggle_handlers():
    """Top control buttons should call the panel toggle functions directly."""
    html = render_chat_tab()

    assert 'onclick="toggleMemoryPanel()"' in html
    assert 'onclick="toggleDebugPanel()"' in html
    assert 'onclick="toggleSettingsPanel()"' in html


def test_chat_tab_renders_all_toggle_panels():
    """Each top-level toggle button should have a corresponding panel in the markup."""
    html = render_chat_tab()

    assert 'id="memory-panel"' in html
    assert 'id="debug-panel"' in html
    assert 'id="settings-panel"' in html


def test_chat_tab_renders_memory_panel_support_sections():
    """The memory sidebar should expose recent memories, equipment, and tool operations."""
    html = render_chat_tab()

    assert 'id="memory-saved-list"' in html
    assert 'id="memory-equipment-list"' in html
    assert 'id="memory-tool-ops-list"' in html


def test_chat_js_has_single_panel_toggle_definitions():
    """Legacy duplicate handlers should not override the panel toggles."""
    js = render_chat_js()

    assert js.count("function toggleMemoryPanel()") == 1
    assert js.count("function toggleDebugPanel()") == 1
    assert js.count("function toggleSettingsPanel()") == 1
    assert "memory-panel-toggle-btn" not in js


def test_chat_js_supports_terminal_history_and_scoped_execute_endpoint():
    """User terminal should support history keys and execute against the persona-scoped sandbox API."""
    js = render_chat_js()

    assert "ArrowUp" in js
    assert "ArrowDown" in js
    assert "/api/chat/' + encodeURIComponent(S.persona) + '/sandbox/execute" in js
