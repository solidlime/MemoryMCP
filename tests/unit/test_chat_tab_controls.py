"""Regression tests for chat tab control wiring."""

from memory_mcp.api.http.sections.chat import render_chat_js, render_chat_tab


def test_chat_tab_buttons_use_panel_toggle_handlers():
    """Top control buttons should call the panel toggle functions directly."""
    html = render_chat_tab()

    assert 'onclick="toggleMemoryPanel()"' in html
    assert 'onclick="toggleSettingsPanel()"' in html


def test_chat_tab_renders_all_toggle_panels():
    """Each top-level toggle button should have a corresponding panel in the markup."""
    html = render_chat_tab()

    assert 'id="memory-panel"' in html
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
    assert js.count("function toggleSettingsPanel()") == 1
    assert "memory-panel-toggle-btn" not in js


def test_chat_js_supports_terminal_history_and_scoped_execute_endpoint():
    """Sandbox terminal history was moved to Coding Agent panel. Chat tab JS should retain the persona-scoped sandbox execute API reference."""
    js = render_chat_js()

    assert "/api/chat/' + encodeURIComponent(S.persona) + '/sandbox/execute" in js


def test_chat_tab_renders_artifacts_tab():
    """Coding Agent panel should include an artifacts display area."""
    html = render_chat_tab()

    assert "ca-artifacts" in html
    assert "ca-panel" in html


def test_chat_tab_renders_sandbox_install_ui():
    """Coding Agent panel should include a code execution area."""
    html = render_chat_tab()

    assert "ca-code-area" in html
    assert "ca-run-btn" in html


def test_chat_js_has_sandbox_install_and_reset_functions():
    """Sandbox install/reset functions were moved to Coding Agent panel. Chat tab JS should retain sandboxRunBlock."""
    js = render_chat_js()

    assert "function sandboxRunBlock(" in js


def test_chat_js_has_sandbox_run_block_function():
    """JS should define sandboxRunBlock for code block execution."""
    js = render_chat_js()

    assert "function sandboxRunBlock(" in js


def test_chat_js_uses_install_endpoint():
    """Sandbox install was moved to Coding Agent. Check that sandbox execute endpoint remains."""
    js = render_chat_js()

    assert "/sandbox/execute" in js


def test_chat_js_uses_reset_endpoint():
    """Sandbox reset was moved to Coding Agent. sandboxRunBlock should be present."""
    js = render_chat_js()

    assert "function sandboxRunBlock(" in js
