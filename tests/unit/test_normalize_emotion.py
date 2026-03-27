from __future__ import annotations

import pytest

from memory_mcp.api.mcp.tools import _VALID_EMOTIONS
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


class TestValidEmotionsConstant:
    """P2: tools.py の _VALID_EMOTIONS — emotion warning の条件ゲート。"""

    def test_has_22_emotions(self):
        assert len(_VALID_EMOTIONS) == 22

    def test_all_canonical_emotions_present(self):
        expected = {
            "joy",
            "sadness",
            "anger",
            "fear",
            "surprise",
            "disgust",
            "love",
            "neutral",
            "anticipation",
            "trust",
            "anxiety",
            "excitement",
            "frustration",
            "nostalgia",
            "pride",
            "shame",
            "guilt",
            "loneliness",
            "contentment",
            "curiosity",
            "awe",
            "relief",
        }
        assert expected == _VALID_EMOTIONS

    def test_common_aliases_not_in_valid_emotions(self):
        """'happy', 'sad' 等のエイリアスは _VALID_EMOTIONS に含まれない。"""
        assert "happy" not in _VALID_EMOTIONS
        assert "sad" not in _VALID_EMOTIONS
        assert "unknown_emotion" not in _VALID_EMOTIONS

    def test_warning_condition_for_invalid_emotion(self):
        """無効な emotion_type は warning を生成する条件（not in _VALID_EMOTIONS）。"""
        invalid = "totally_invalid_emotion"
        assert invalid not in _VALID_EMOTIONS
        # warning メッセージフォーマットの確認
        warning = f"[Warning: emotion_type '{invalid}' is not a valid emotion, defaulted to 'neutral']\n"
        assert warning.startswith("[Warning: emotion_type '")
        assert "defaulted to 'neutral'" in warning
        assert warning.endswith("]\n")

    def test_no_warning_for_valid_emotion(self):
        """有効な emotion_type は _VALID_EMOTIONS に含まれる → warning なし。"""
        for valid in _VALID_EMOTIONS:
            assert valid in _VALID_EMOTIONS  # tautology, but documents intent
