"""Tests for dashboard goals/promises normalization logic.

Verifies the list comprehension used in persona.py lines 109/113.
Does NOT duplicate test_goals_promises.py which covers DB persistence.
"""


def _normalize_goals(raw: list[dict]) -> list[str]:
    """Replicate the normalization from persona.py line 109."""
    return [g["description"] for g in raw if g.get("status") == "active" and g.get("description")]


def _normalize_promises(raw: list[dict]) -> list[str]:
    """Replicate the normalization from persona.py line 113."""
    return [p["description"] for p in raw if p.get("status") == "active" and p.get("description")]


def test_goals_normalization_active_only():
    """active な goals のみ返される。"""
    raw = [
        {"id": "g1", "description": "Do X", "status": "active"},
        {"id": "g2", "description": "Done Y", "status": "inactive"},
        {"id": "g3", "description": "Do Z", "status": "active"},
    ]
    result = _normalize_goals(raw)
    assert result == ["Do X", "Do Z"]
    assert "Done Y" not in result


def test_goals_normalization_empty_description_filtered():
    """description が空の active goal はスキップされる。"""
    raw = [
        {"id": "g1", "description": "", "status": "active"},
        {"id": "g2", "description": "Do X", "status": "active"},
    ]
    result = _normalize_goals(raw)
    assert "" not in result
    assert result == ["Do X"]


def test_goals_normalization_missing_fields():
    """status/description キーがない行はスキップされる。"""
    raw = [
        {"id": "g1"},  # status/description 欠如
        {"id": "g2", "description": "Goal A", "status": "active"},
    ]
    result = _normalize_goals(raw)
    assert result == ["Goal A"]


def test_promises_normalization_logic():
    """active な promises のみ返される。"""
    raw = [
        {"description": "Promise A", "status": "active"},
        {"description": "Promise B", "status": "inactive"},
    ]
    result = _normalize_promises(raw)
    assert result == ["Promise A"]


def test_empty_list_returns_empty():
    """空リストを渡すと空リストが返る。"""
    assert _normalize_goals([]) == []
    assert _normalize_promises([]) == []
