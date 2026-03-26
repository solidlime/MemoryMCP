import pytest

from memory_mcp.domain.value_objects import normalize_emotion


@pytest.mark.parametrize(
    "input_text,expected",
    [
        ("joy", "joy"),
        ("happy", "joy"),
        ("嬉しい", "joy"),
        ("sad", "sadness"),
        ("悲しい", "sadness"),
        ("angry", "anger"),
        ("怒り", "anger"),
        ("anxiety", "anxiety"),
        ("心配", "anxiety"),
        ("excited", "excitement"),
        ("わくわく", "excitement"),
        ("neutral", "neutral"),
        ("", "neutral"),
        (None, "neutral"),
        ("totally_unknown_xyzzy", "neutral"),
        ("relief", "relief"),
        ("ほっとする", "relief"),
    ],
)
def test_normalize_emotion(input_text, expected):
    assert normalize_emotion(input_text) == expected
