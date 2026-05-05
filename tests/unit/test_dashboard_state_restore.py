"""Regression tests for dashboard state restoration helpers."""

from memory_mcp.api.http.sections.base import render_utilities_js


def test_dashboard_uses_consistent_persona_storage_helpers():
    """Persona persistence should use shared helpers instead of split localStorage keys."""
    js = render_utilities_js()

    assert "function getStoredPersona()" in js
    assert "function setStoredPersona(persona)" in js
    assert "localStorage.setItem('selected_persona'" in js
    assert "localStorage.setItem('mmcp-persona'" in js
