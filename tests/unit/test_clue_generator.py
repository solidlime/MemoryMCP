"""Unit tests for ClueGenerator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from memory_mcp.domain.search.clue_generator import ClueGenerator, _parse_clues


class TestParseClues:
    def test_valid_json_array(self):
        result = _parse_clues('["clue one", "clue two", "clue three"]')
        assert result == ["clue one", "clue two", "clue three"]

    def test_json_array_truncated_to_3(self):
        result = _parse_clues('["a", "b", "c", "d"]')
        assert len(result) == 3

    def test_fallback_quoted_strings(self):
        result = _parse_clues('Here are the clues: "first clue" and "second clue"')
        assert "first clue" in result
        assert "second clue" in result

    def test_empty_on_garbage(self):
        result = _parse_clues("no clues here at all")
        assert result == []


class TestClueGeneratorNoLLM:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_api_key(self):
        gen = ClueGenerator()
        config = MagicMock()
        config.extract_model = ""
        config.get_effective_model.return_value = "gpt-4"
        config.get_effective_api_key.return_value = ""
        config.get_effective_base_url.return_value = "https://api.openai.com/v1"
        result = await gen.generate("context", "query", config)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_model(self):
        gen = ClueGenerator()
        config = MagicMock()
        config.extract_model = ""
        config.get_effective_model.return_value = ""
        config.get_effective_api_key.return_value = "sk-test"
        result = await gen.generate("context", "query", config)
        assert result == []
