"""Unit tests for MentalModel dataclass and _parse_models()."""

from __future__ import annotations

import json
from datetime import datetime

from nous.application.chat.pattern_detector import _parse_models
from nous.domain.memory.mental_model import MentalModel


class TestMentalModelDataclass:
    """Tests for the MentalModel dataclass."""

    def test_minimal_creation(self):
        model = MentalModel(content="ユーザーは朝コーヒーを飲む習慣がある")
        assert model.content == "ユーザーは朝コーヒーを飲む習慣がある"
        assert model.source_memory_keys == []
        assert model.confidence == 0.7
        assert model.abstracted_at is None
        assert model.type_tag == ""

    def test_with_all_fields(self):
        now = datetime.now()
        model = MentalModel(
            content="ユーザーはReact hooksの理解に苦労する傾向がある",
            source_memory_keys=["mem_001", "mem_002", "mem_003"],
            confidence=0.85,
            abstracted_at=now,
            type_tag="problem",
        )
        assert model.content == "ユーザーはReact hooksの理解に苦労する傾向がある"
        assert model.source_memory_keys == ["mem_001", "mem_002", "mem_003"]
        assert model.confidence == 0.85
        assert model.abstracted_at == now
        assert model.type_tag == "problem"

    def test_default_confidence(self):
        model = MentalModel(content="test")
        assert model.confidence == 0.7

    def test_source_memory_keys_mutable(self):
        model = MentalModel(content="test")
        model.source_memory_keys.append("key_001")
        assert model.source_memory_keys == ["key_001"]

    def test_equality(self):
        model1 = MentalModel(content="pattern")
        model2 = MentalModel(content="pattern")
        assert model1.content == model2.content
        # MentalModel is not frozen, so equality check is by identity not value
        assert model1 is not model2


class TestParseModels:
    """Tests for the _parse_models() JSON parser."""

    def test_valid_json_two_models(self):
        raw = json.dumps({"models": ["モデルA", "モデルB"]})
        result = _parse_models(raw)
        assert result == ["モデルA", "モデルB"]

    def test_valid_json_three_models(self):
        raw = json.dumps({"models": ["a", "b", "c"]})
        result = _parse_models(raw)
        assert result == ["a", "b", "c"]

    def test_code_fenced_json_is_parsed(self):
        raw = '```json\n{"models": ["x", "y", "z"]}\n```'
        result = _parse_models(raw)
        assert result == ["x", "y", "z"]

    def test_code_fenced_no_lang_tag(self):
        raw = '```\n{"models": ["p", "q"]}\n```'
        result = _parse_models(raw)
        assert result == ["p", "q"]

    def test_invalid_json_returns_empty(self):
        result = _parse_models("これはJSONではありません")
        assert result == []

    def test_empty_string_returns_empty(self):
        result = _parse_models("")
        assert result == []

    def test_empty_models_list(self):
        raw = json.dumps({"models": []})
        result = _parse_models(raw)
        assert result == []

    def test_non_string_items_filtered_out(self):
        raw = json.dumps({"models": ["valid", 42, None, "also valid"]})
        result = _parse_models(raw)
        assert result == ["valid", "also valid"]

    def test_whitespace_only_items_filtered(self):
        raw = json.dumps({"models": ["  ", "real insight", "\t\n"]})
        result = _parse_models(raw)
        assert result == ["real insight"]

    def test_missing_models_key(self):
        raw = json.dumps({"data": ["a", "b"]})
        result = _parse_models(raw)
        assert result == []

    def test_leading_trailing_whitespace_stripped(self):
        raw = "  " + json.dumps({"models": ["trimmed"]}) + "\n"
        result = _parse_models(raw)
        assert result == ["trimmed"]

    def test_partial_json_returns_empty(self):
        result = _parse_models('{"models": ["incomplete"')
        assert result == []
