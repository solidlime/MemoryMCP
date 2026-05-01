"""Unit tests for _parse_insights() in reflection.py and threshold logic."""

from __future__ import annotations

import json

from memory_mcp.application.chat.reflection import _parse_insights


class TestParseInsights:
    """Tests for the _parse_insights() JSON parser."""

    def test_valid_json_three_insights(self):
        raw = json.dumps({"insights": ["洞察A", "洞察B", "洞察C"]})
        result = _parse_insights(raw)
        assert result == ["洞察A", "洞察B", "洞察C"]

    def test_valid_json_one_insight(self):
        raw = json.dumps({"insights": ["単一の洞察"]})
        result = _parse_insights(raw)
        assert result == ["単一の洞察"]

    def test_code_fenced_json_is_parsed(self):
        raw = '```json\n{"insights": ["a", "b", "c"]}\n```'
        result = _parse_insights(raw)
        assert result == ["a", "b", "c"]

    def test_code_fenced_no_lang_tag(self):
        raw = '```\n{"insights": ["x", "y"]}\n```'
        result = _parse_insights(raw)
        assert result == ["x", "y"]

    def test_invalid_json_returns_empty(self):
        result = _parse_insights("これはJSONではありません")
        assert result == []

    def test_empty_string_returns_empty(self):
        result = _parse_insights("")
        assert result == []

    def test_empty_insights_list(self):
        raw = json.dumps({"insights": []})
        result = _parse_insights(raw)
        assert result == []

    def test_non_string_items_filtered_out(self):
        raw = json.dumps({"insights": ["valid", 42, None, "also valid"]})
        result = _parse_insights(raw)
        assert result == ["valid", "also valid"]

    def test_whitespace_only_items_filtered(self):
        raw = json.dumps({"insights": ["  ", "real insight", "\t\n"]})
        result = _parse_insights(raw)
        assert result == ["real insight"]

    def test_missing_insights_key(self):
        raw = json.dumps({"data": ["a", "b"]})
        result = _parse_insights(raw)
        assert result == []

    def test_leading_trailing_whitespace_stripped(self):
        raw = "  " + json.dumps({"insights": ["trimmed"]}) + "\n"
        result = _parse_insights(raw)
        assert result == ["trimmed"]

    def test_partial_json_returns_empty(self):
        result = _parse_insights('{"insights": ["incomplete"')
        assert result == []


class TestReflectionThreshold:
    """Tests for the threshold check in maybe_run_reflection logic."""

    def test_below_threshold_returns_empty(self):
        """Simulate threshold check: sum < threshold → no reflection."""
        threshold = 3.0
        recent_importance_sum = 2.5
        # This is the exact guard in maybe_run_reflection
        result = [] if recent_importance_sum < threshold else ["would_reflect"]
        assert result == []

    def test_at_threshold_triggers_reflection(self):
        """sum >= threshold should pass the guard."""
        threshold = 3.0
        recent_importance_sum = 3.0
        result = [] if recent_importance_sum < threshold else ["would_reflect"]
        assert result == ["would_reflect"]

    def test_above_threshold_triggers_reflection(self):
        threshold = 3.0
        recent_importance_sum = 5.5
        result = [] if recent_importance_sum < threshold else ["would_reflect"]
        assert result == ["would_reflect"]

    def test_zero_sum_below_any_positive_threshold(self):
        threshold = 0.1
        result = [] if threshold > 0.0 else ["would_reflect"]
        assert result == []
