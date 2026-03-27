"""Tests for update_context append_goals / append_promises merge logic.

These tests verify the deduplication logic used in tools.py lines 627/635.
They do NOT duplicate test_goals_promises.py which covers persistence/roundtrip.
"""

import json


def _merge(existing_json: str | list, append: list[str]) -> list[str]:
    """Replicate the merge logic from tools.py."""
    if isinstance(existing_json, str):
        try:
            existing = json.loads(existing_json)
        except Exception:
            existing = []
    elif isinstance(existing_json, list):
        existing = existing_json
    else:
        existing = []
    return existing + [g for g in append if g and g not in existing]


def test_append_goals_merges_with_existing():
    """append_goals は既存リストに追記する（重複なし）。"""
    merged = _merge('["goal1"]', ["goal2"])
    assert merged == ["goal1", "goal2"]


def test_append_deduplication():
    """append_goals は重複を追加しない。"""
    merged = _merge(["Do X", "Do Y"], ["Do X", "Do Z"])
    assert merged == ["Do X", "Do Y", "Do Z"]
    assert merged.count("Do X") == 1


def test_append_empty_strings_filtered():
    """空文字列はappendされない。"""
    merged = _merge(["goal1"], ["", "goal2"])
    assert "" not in merged
    assert "goal2" in merged
    assert merged == ["goal1", "goal2"]


def test_append_to_empty_existing():
    """既存が空リストの場合でも正しく追加される。"""
    merged = _merge("[]", ["new_goal"])
    assert merged == ["new_goal"]


def test_append_invalid_json_treated_as_empty():
    """既存値がJSON不正な場合は空リストとして扱う。"""
    merged = _merge("not-valid-json", ["goal1"])
    assert merged == ["goal1"]


def test_append_existing_as_list_directly():
    """既存がリスト型の場合も正しくマージされる。"""
    merged = _merge(["A", "B"], ["B", "C"])
    assert merged == ["A", "B", "C"]


def test_append_none_items_filtered():
    """None は None チェック（`if g`）でフィルタされる。"""
    merged = _merge(["goal1"], [None, "goal2"])  # type: ignore[list-item]
    assert None not in merged
    assert merged == ["goal1", "goal2"]
