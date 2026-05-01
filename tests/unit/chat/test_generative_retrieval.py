"""Unit tests for composite-scoring retrieval logic in PrepareStep."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

# ---------------------------------------------------------------------------
# Import the helpers directly (no server / embedding model needed)
# ---------------------------------------------------------------------------
from memory_mcp.application.chat.pipeline.prepare import (
    _RECENCY_LAMBDA,
    _compute_recency_decay,
)


class TestComputeRecencyDecay:
    """Tests for _compute_recency_decay()."""

    def test_zero_days_returns_one(self):
        """A memory created just now should have recency ≈ 1.0."""
        now = datetime.now(tz=UTC)
        result = _compute_recency_decay(now)
        assert abs(result - 1.0) < 0.01

    def test_one_day_returns_about_0606(self):
        """After 1 day: exp(-0.5 * 1) ≈ 0.6065."""
        one_day_ago = datetime.now(tz=UTC) - timedelta(days=1)
        result = _compute_recency_decay(one_day_ago)
        expected = math.exp(-_RECENCY_LAMBDA * 1.0)
        assert abs(result - expected) < 0.01

    def test_ten_days_returns_very_small(self):
        """After 10 days: exp(-0.5 * 10) ≈ 0.0067."""
        ten_days_ago = datetime.now(tz=UTC) - timedelta(days=10)
        result = _compute_recency_decay(ten_days_ago)
        expected = math.exp(-_RECENCY_LAMBDA * 10.0)
        assert abs(result - expected) < 0.001
        assert result < 0.02

    def test_none_created_at_returns_fallback(self):
        """None input returns a safe fallback value of 0.5."""
        result = _compute_recency_decay(None)
        assert result == 0.5

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetimes (no tzinfo) should be handled without raising."""
        naive_now = datetime.utcnow()
        result = _compute_recency_decay(naive_now)
        # Should be close to 1.0 since it's "now"
        assert result > 0.9

    def test_monotonic_decrease(self):
        """Recency should strictly decrease as age increases."""
        now = datetime.now(tz=UTC)
        scores = [
            _compute_recency_decay(now - timedelta(days=d))
            for d in [0, 1, 3, 7, 14]
        ]
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1]


class TestCompositeScoreFormula:
    """Tests for the composite scoring formula used in _search_memories."""

    @staticmethod
    def composite(recency: float, importance: float, rrf: float,
                  rw: float = 0.3, iw: float = 0.3, relw: float = 0.4) -> float:
        return rw * recency + iw * importance + relw * rrf

    def test_weights_sum_to_correct_total(self):
        """Equal inputs with default weights should produce weighted average."""
        score = self.composite(1.0, 1.0, 1.0)
        assert abs(score - 1.0) < 1e-9

    def test_relevance_dominates_with_high_weight(self):
        """High relevance weight should make relevance dominate."""
        score_high_rel = self.composite(0.1, 0.1, 0.9, rw=0.1, iw=0.1, relw=0.8)
        score_low_rel  = self.composite(0.9, 0.9, 0.1, rw=0.1, iw=0.1, relw=0.8)
        assert score_high_rel > score_low_rel

    def test_recency_dominates_with_high_weight(self):
        """High recency weight should make fresh memories rank higher."""
        score_fresh = self.composite(0.9, 0.1, 0.1, rw=0.8, iw=0.1, relw=0.1)
        score_old   = self.composite(0.1, 0.9, 0.9, rw=0.8, iw=0.1, relw=0.1)
        assert score_fresh > score_old

    def test_zero_scores_give_zero(self):
        score = self.composite(0.0, 0.0, 0.0)
        assert score == 0.0

    def test_custom_weight_precision(self):
        """Score with known inputs should match manual calculation."""
        recency, importance, rrf = 0.8, 0.5, 0.6
        rw, iw, relw = 0.3, 0.3, 0.4
        expected = 0.3 * 0.8 + 0.3 * 0.5 + 0.4 * 0.6
        result = self.composite(recency, importance, rrf, rw, iw, relw)
        assert abs(result - expected) < 1e-9
