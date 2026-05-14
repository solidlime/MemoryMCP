"""Tests for MemoryEnricher — importance + relation extraction via mocked LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_mcp.domain.memory.enrichment import EnrichmentResult, RelationCandidate
from memory_mcp.infrastructure.llm.base import DoneEvent, TextDeltaEvent
from memory_mcp.infrastructure.llm.memory_enricher import MemoryEnricher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
def enricher() -> MemoryEnricher:
    return MemoryEnricher(
        provider="openrouter",
        api_key="test-key",
        model="test-model",
        base_url="https://test.url/v1",
        min_chars=10,
    )


@pytest.fixture
def mock_get_provider():
    """Fixture that patches get_provider and returns a mock factory.

    Usage::
        mock_provider, mock_factory = mock_get_provider
        mock_provider.stream.return_value = _async_iter(events...)
    """
    with patch("memory_mcp.infrastructure.llm.memory_enricher.get_provider") as mock:
        mock_provider = MagicMock()
        mock.return_value = mock_provider
        yield mock_provider, mock


def _async_iter(*events: Any):
    """Build an async generator that yields the given events."""

    async def _gen():
        for evt in events:
            yield evt

    return _gen()


class TestMinChars:
    def test_skip_short_content(self, enricher: MemoryEnricher):
        """Content shorter than min_chars returns None."""
        result = enricher.enrich(content="hi", type_tags=[], entities=[])
        assert result is None

    def test_skip_empty_content(self, enricher: MemoryEnricher):
        result = enricher.enrich(content="", type_tags=[], entities=[])
        assert result is None

    def test_skip_whitespace_only(self, enricher: MemoryEnricher):
        result = enricher.enrich(content="   ", type_tags=[], entities=[])
        assert result is None


class TestParseImportance:
    def test_importance_parsed_correctly(self, enricher: MemoryEnricher, mock_get_provider):
        """LLM response with importance 0.8 is parsed correctly."""
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content='{"importance": 0.8, "relations": []}'),
            DoneEvent(full_content='{"importance": 0.8, "relations": []}'),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。テスト用です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert result.importance == 0.8

    def test_importance_clamped_high(self, enricher: MemoryEnricher, mock_get_provider):
        """Importance is clamped to [0.0, 1.0]."""
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content='{"importance": 2.5, "relations": []}'),
            DoneEvent(full_content='{"importance": 2.5, "relations": []}'),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。テスト用です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert result.importance == 1.0

    def test_importance_clamped_low(self, enricher: MemoryEnricher, mock_get_provider):
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content='{"importance": -1.0, "relations": []}'),
            DoneEvent(full_content='{"importance": -1.0, "relations": []}'),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert result.importance == 0.0

    def test_importance_default_when_missing(self, enricher: MemoryEnricher, mock_get_provider):
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content='{"relations": []}'),
            DoneEvent(full_content='{"relations": []}'),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert result.importance == 0.5


class TestParseRelations:
    def test_relations_parsed_correctly(self, enricher: MemoryEnricher, mock_get_provider):
        """LLM response with relations is parsed correctly."""
        json_text = (
            '{"importance": 0.7, "relations": ['
            '{"source": "Alice", "target": "Bob", "type": "knows", "confidence": 0.9},'
            '{"source": "Charlie", "target": "ProjectX", "type": "created", "confidence": 0.8}'
            "]}"
        )
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content=json_text),
            DoneEvent(full_content=json_text),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert len(result.relations) == 2

        rel0 = result.relations[0]
        assert rel0.source_entity == "Alice"
        assert rel0.target_entity == "Bob"
        assert rel0.relation_type == "knows"
        assert rel0.confidence == 0.9

        rel1 = result.relations[1]
        assert rel1.source_entity == "Charlie"
        assert rel1.target_entity == "ProjectX"
        assert rel1.relation_type == "created"
        assert rel1.confidence == 0.8

    def test_empty_relations(self, enricher: MemoryEnricher, mock_get_provider):
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content='{"importance": 0.5, "relations": []}'),
            DoneEvent(full_content='{"importance": 0.5, "relations": []}'),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert result.relations == []

    def test_invalid_relation_type_skipped(self, enricher: MemoryEnricher, mock_get_provider):
        """Relation types not in VALID_RELATION_TYPES are skipped."""
        json_text = (
            '{"importance": 0.5, "relations": ['
            '{"source": "Alice", "target": "Bob", "type": "invalid_type", "confidence": 0.9},'
            '{"source": "Charlie", "target": "Dave", "type": "knows", "confidence": 0.8}'
            "]}"
        )
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content=json_text),
            DoneEvent(full_content=json_text),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert len(result.relations) == 1
        assert result.relations[0].source_entity == "Charlie"

    def test_missing_source_target_skipped(self, enricher: MemoryEnricher, mock_get_provider):
        json_text = (
            '{"importance": 0.5, "relations": ['
            '{"source": "", "target": "Bob", "type": "knows", "confidence": 0.9},'
            '{"source": "Alice", "target": "", "type": "knows", "confidence": 0.9}'
            "]}"
        )
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content=json_text),
            DoneEvent(full_content=json_text),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert result.relations == []


class TestErrorHandling:
    def test_returns_none_on_llm_error(self, enricher: MemoryEnricher, mock_get_provider):
        """When LLM returns an ErrorEvent, enrich returns None."""
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            DoneEvent(full_content=""),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        # DoneEvent with no TextDeltaEvent means empty content → _parse_response returns None
        assert result is None

    def test_returns_none_on_invalid_json(self, enricher: MemoryEnricher, mock_get_provider):
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content="not valid json"),
            DoneEvent(full_content="not valid json"),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is None

    def test_returns_none_on_provider_exception(self, enricher: MemoryEnricher, mock_get_provider):
        """When get_provider raises, enrich returns None without crashing."""
        _, mock_factory = mock_get_provider
        mock_factory.side_effect = RuntimeError("Provider unavailable")

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is None


class TestMarkdownCodeBlock:
    def test_parse_json_from_markdown_block(self, enricher: MemoryEnricher, mock_get_provider):
        """LLM may return JSON inside ```json ... ``` block."""
        md_text = (
            "Here is the analysis:\n\n"
            '```json\n{"importance": 0.9, "relations": []}\n```\n'
        )
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content=md_text),
            DoneEvent(full_content=md_text),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert result is not None
        assert result.importance == 0.9


class TestEnrichmentResult:
    def test_result_is_enrichmentresult_instance(self, enricher: MemoryEnricher, mock_get_provider):
        mock_provider, _ = mock_get_provider
        mock_provider.stream.return_value = _async_iter(
            TextDeltaEvent(content='{"importance": 0.6, "relations": []}'),
            DoneEvent(full_content='{"importance": 0.6, "relations": []}'),
        )

        result = enricher.enrich(
            content="これは十分に長いメモリの内容です。",
            type_tags=[],
            entities=[],
        )
        assert isinstance(result, EnrichmentResult)

    def test_relation_candidate_dataclass(self):
        rel = RelationCandidate(
            source_entity="Alice",
            target_entity="Bob",
            relation_type="knows",
            confidence=0.95,
        )
        assert rel.source_entity == "Alice"
        assert rel.target_entity == "Bob"
        assert rel.relation_type == "knows"
        assert rel.confidence == 0.95
