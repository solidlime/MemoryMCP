"""Unit tests for memory_mcp.api.mcp.middleware — persona resolution."""

from __future__ import annotations

import pytest

from memory_mcp.api.mcp.middleware import (
    PersonaMiddleware,
    _persona_var,
    get_current_persona,
    resolve_persona_from_headers,
    resolve_persona_from_token,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _noop_send(msg: dict) -> None:  # noqa: ARG001
    """No-op ASGI send callable."""


# =========================================================================
# A. resolve_persona_from_headers()
# =========================================================================


class TestResolvePersonaFromHeaders:
    def test_bearer_token_highest_priority(self):
        """Bearerトークンが最優先"""
        result = resolve_persona_from_headers(
            authorization="Bearer alice",
            x_persona="bob",
        )
        assert result == "alice"

    def test_x_persona_over_env(self, monkeypatch):
        """X-Personaが環境変数より優先"""
        monkeypatch.setenv("PERSONA", "env_persona")
        result = resolve_persona_from_headers(x_persona="header_persona")
        assert result == "header_persona"

    def test_env_fallback(self, monkeypatch):
        """ヘッダーなしで環境変数フォールバック"""
        monkeypatch.setenv("PERSONA", "env_persona")
        result = resolve_persona_from_headers()
        assert result == "env_persona"

    def test_default_persona_env(self, monkeypatch):
        """PERSONAなし、MEMORY_MCP_DEFAULT_PERSONA使用"""
        monkeypatch.delenv("PERSONA", raising=False)
        monkeypatch.setenv("MEMORY_MCP_DEFAULT_PERSONA", "fallback")
        result = resolve_persona_from_headers()
        assert result == "fallback"

    def test_ultimate_default(self, monkeypatch):
        """全てなしで 'default' 返却"""
        monkeypatch.delenv("PERSONA", raising=False)
        monkeypatch.delenv("MEMORY_MCP_DEFAULT_PERSONA", raising=False)
        result = resolve_persona_from_headers()
        assert result == "default"

    def test_bearer_whitespace_stripped(self):
        """Bearerトークンの空白はstrip"""
        result = resolve_persona_from_headers(authorization="Bearer  alice  ")
        assert result == "alice"

    def test_empty_bearer_falls_through(self, monkeypatch):
        """Bearer直後が空なら次に落ちる"""
        monkeypatch.delenv("PERSONA", raising=False)
        monkeypatch.delenv("MEMORY_MCP_DEFAULT_PERSONA", raising=False)
        result = resolve_persona_from_headers(
            authorization="Bearer   ",
            x_persona="bob",
        )
        assert result == "bob"

    def test_empty_x_persona_falls_through(self, monkeypatch):
        """X-Personaが空文字列なら次に落ちる"""
        monkeypatch.setenv("PERSONA", "env_persona")
        result = resolve_persona_from_headers(x_persona="  ")
        assert result == "env_persona"


# =========================================================================
# B. get_current_persona()
# =========================================================================


class TestGetCurrentPersona:
    def test_returns_contextvar_value(self):
        """contextvarにセットされた値を返す"""
        token = _persona_var.set("ctx_persona")
        try:
            assert get_current_persona() == "ctx_persona"
        finally:
            _persona_var.reset(token)

    def test_fallback_to_env(self, monkeypatch):
        """contextvar未セット時は環境変数"""
        monkeypatch.setenv("PERSONA", "env_persona")
        assert get_current_persona() == "env_persona"

    def test_fallback_to_default(self, monkeypatch):
        """contextvar未セット、環境変数もなし → 'default'"""
        monkeypatch.delenv("PERSONA", raising=False)
        monkeypatch.delenv("MEMORY_MCP_DEFAULT_PERSONA", raising=False)
        assert get_current_persona() == "default"


# =========================================================================
# C. resolve_persona_from_token() 後方互換
# =========================================================================


class TestResolvePersonaFromToken:
    def test_with_bearer(self):
        result = resolve_persona_from_token("Bearer alice")
        assert result == "alice"

    def test_without_bearer(self, monkeypatch):
        monkeypatch.setenv("PERSONA", "env_persona")
        result = resolve_persona_from_token(None)
        assert result == "env_persona"


# =========================================================================
# D. PersonaMiddleware (ASGI level)
# =========================================================================


class TestPersonaMiddleware:
    """ASGIミドルウェアの統合テスト"""

    async def test_bearer_header(self):
        """Authorization Bearerヘッダーでペルソナ解決"""
        captured_persona = None

        async def app(scope, receive, send):  # noqa: ARG001
            nonlocal captured_persona
            captured_persona = get_current_persona()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = PersonaMiddleware(app)
        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer alice")],
        }
        await middleware(scope, None, lambda msg: _noop_send(msg))
        assert captured_persona == "alice"

    async def test_x_persona_header(self):
        """X-Personaヘッダーでペルソナ解決"""
        captured_persona = None

        async def app(scope, receive, send):  # noqa: ARG001
            nonlocal captured_persona
            captured_persona = get_current_persona()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = PersonaMiddleware(app)
        scope = {
            "type": "http",
            "headers": [(b"x-persona", b"bob")],
        }
        await middleware(scope, None, lambda msg: _noop_send(msg))
        assert captured_persona == "bob"

    async def test_bearer_over_x_persona(self):
        """BearerがX-Personaより優先"""
        captured_persona = None

        async def app(scope, receive, send):  # noqa: ARG001
            nonlocal captured_persona
            captured_persona = get_current_persona()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = PersonaMiddleware(app)
        scope = {
            "type": "http",
            "headers": [
                (b"authorization", b"Bearer alice"),
                (b"x-persona", b"bob"),
            ],
        }
        await middleware(scope, None, lambda msg: _noop_send(msg))
        assert captured_persona == "alice"

    async def test_no_headers_fallback(self, monkeypatch):
        """ヘッダーなしで環境変数フォールバック"""
        monkeypatch.setenv("PERSONA", "env_persona")
        captured_persona = None

        async def app(scope, receive, send):  # noqa: ARG001
            nonlocal captured_persona
            captured_persona = get_current_persona()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = PersonaMiddleware(app)
        scope = {"type": "http", "headers": []}
        await middleware(scope, None, lambda msg: _noop_send(msg))
        assert captured_persona == "env_persona"

    async def test_contextvar_reset_after_request(self):
        """リクエスト後にcontextvarがリセットされる"""

        async def app(scope, receive, send):  # noqa: ARG001
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = PersonaMiddleware(app)
        scope = {
            "type": "http",
            "headers": [(b"x-persona", b"temp_persona")],
        }
        await middleware(scope, None, lambda msg: _noop_send(msg))
        assert _persona_var.get() == ""

    async def test_non_http_scope_passthrough(self):
        """非HTTPスコープはパススルー"""
        called = False

        async def app(scope, receive, send):  # noqa: ARG001
            nonlocal called
            called = True

        middleware = PersonaMiddleware(app)
        scope = {"type": "websocket"}
        await middleware(scope, None, None)
        assert called is True


# =========================================================================
# E. _resolve_persona() in tools.py
# =========================================================================


class TestResolvePersonaInTools:
    def test_uses_get_current_persona(self):
        """tools._resolve_persona()がget_current_persona()を経由"""
        import memory_mcp.api.mcp.tools as tools_module

        token = _persona_var.set("tool_persona")
        try:
            result = tools_module._resolve_persona()
            assert result == "tool_persona"
        finally:
            _persona_var.reset(token)
