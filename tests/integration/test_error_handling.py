"""Tests for error responses: no exception detail leakage."""
import inspect


def test_routers_import_without_error():
    """全ルーターが正しくインポートできること（構文エラーチェック）。"""
    from memory_mcp.api.http.routers import admin, item, memory, persona, search

    assert admin is not None
    assert item is not None
    assert memory is not None
    assert persona is not None
    assert search is not None


def test_error_response_does_not_leak_exception_details():
    """各ルーターが str(exc) をレスポンスに含めていないことを確認。"""
    from memory_mcp.api.http.routers import admin, item, memory, persona, search

    for module in (admin, item, memory, persona, search):
        source = inspect.getsource(module)
        assert '"error": str(exc)' not in source, (
            f"{module.__name__} leaks exception detail via str(exc)"
        )


def test_internal_server_error_string_present_in_routers():
    """各ルーターに 'Internal server error' フォーマットが使われている。"""
    from memory_mcp.api.http.routers import admin, item, memory, persona, search

    for module in (admin, item, memory, persona, search):
        source = inspect.getsource(module)
        assert "Internal server error" in source, (
            f"{module.__name__} missing 'Internal server error' error response"
        )
