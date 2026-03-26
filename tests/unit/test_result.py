"""Tests for Result type (Success / Failure)."""

import pytest

from memory_mcp.domain.shared.result import Failure, Success


class TestSuccess:
    def test_create_with_value(self):
        r = Success(42)
        assert r.value == 42

    def test_is_ok_true(self):
        assert Success("hello").is_ok is True

    def test_unwrap_returns_value(self):
        assert Success("data").unwrap() == "data"

    def test_unwrap_or_returns_value(self):
        assert Success(10).unwrap_or(99) == 10

    def test_map_transforms_value(self):
        r = Success(3).map(lambda x: x * 2)
        assert isinstance(r, Success)
        assert r.value == 6

    def test_map_chain(self):
        r = Success(2).map(lambda x: x + 1).map(lambda x: x * 10)
        assert r.value == 30

    def test_frozen(self):
        r = Success(1)
        with pytest.raises(AttributeError):
            r.value = 2  # type: ignore[misc]


class TestFailure:
    def test_create_with_error(self):
        r = Failure("err")
        assert r.error == "err"

    def test_is_ok_false(self):
        assert Failure("err").is_ok is False

    def test_unwrap_raises(self):
        with pytest.raises(ValueError, match="Unwrap on Failure"):
            Failure("bad").unwrap()

    def test_unwrap_or_returns_default(self):
        assert Failure("err").unwrap_or(42) == 42

    def test_map_returns_self(self):
        original = Failure("err")
        mapped = original.map(lambda x: x * 2)
        assert isinstance(mapped, Failure)
        assert mapped.error == "err"

    def test_frozen(self):
        r = Failure("err")
        with pytest.raises(AttributeError):
            r.error = "new"  # type: ignore[misc]


class TestResultUnion:
    """Result = Success | Failure の使い分けテスト。"""

    def test_success_branch(self):
        result: Success[int] | Failure[str] = Success(1)
        if result.is_ok:
            assert result.unwrap() == 1
        else:
            pytest.fail("Expected Success")

    def test_failure_branch(self):
        result: Success[int] | Failure[str] = Failure("oops")
        if not result.is_ok:
            assert result.unwrap_or(0) == 0
        else:
            pytest.fail("Expected Failure")
