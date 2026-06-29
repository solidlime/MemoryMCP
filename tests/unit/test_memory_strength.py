"""FSRS v6 power-law compute_recall() tests."""

import math

import pytest

from nous.domain.memory.entities import MemoryStrength


class TestFSRSRecall:
    """FSRS v6 power-law compute_recall() unit tests."""

    def test_fresh_memory_r_approx_one(self):
        """t=0 → R ≈ 1.0 (brand new memory)."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        assert ms.compute_recall(0.0) == pytest.approx(1.0, abs=1e-6)

    def test_one_stability_period_r_approx_0_224(self):
        """t = stability*24h, S=1 → R ≈ 0.224 (canonical FSRS)."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        r = ms.compute_recall(24.0)  # 1 day = 1 stability period
        expected = 20 ** (-0.5)
        assert r == pytest.approx(expected, abs=1e-6)

    def test_ten_periods_significant_decay(self):
        """t = 10*stability*24h → R < 0.1."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        r = ms.compute_recall(10 * 24.0)
        assert r < 0.1

    def test_zero_stability_returns_zero(self):
        """stability=0 → R = 0.0."""
        ms = MemoryStrength(memory_key="test", stability=0.0)
        assert ms.compute_recall(24.0) == 0.0

        ms2 = MemoryStrength(memory_key="test", stability=-1.0)
        assert ms2.compute_recall(24.0) == 0.0

    def test_exponent_one_steeper_decay(self):
        """decay_exponent=1.0 → steeper decay than 0.5."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        r_default = ms.compute_recall(24.0)  # exponent=0.5
        r_steeper = ms.compute_recall(24.0, decay_exponent=1.0)
        assert r_steeper < r_default

    def test_exponent_two_even_steeper(self):
        """decay_exponent=2.0 → even steeper."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        r_1 = ms.compute_recall(24.0, decay_exponent=1.0)
        r_2 = ms.compute_recall(24.0, decay_exponent=2.0)
        assert r_2 < r_1

    def test_exponent_small_slower_decay(self):
        """decay_exponent=0.1 → slower decay."""
        ms = MemoryStrength(memory_key="test", stability=1.0)
        r_default = ms.compute_recall(24.0)  # exponent=0.5
        r_slow = ms.compute_recall(24.0, decay_exponent=0.1)
        assert r_slow > r_default

    def test_max_stability_long_term_survival(self):
        """S=365 (max), t=1 year → R > 0.05 (long-term survival)."""
        ms = MemoryStrength(memory_key="test", stability=365.0)
        r = ms.compute_recall(365 * 24.0)  # 1 year
        assert r > 0.05

    def test_crossover_with_ebbinghaus(self):
        """FSRS decays faster at short times but slower at long times (heavier tail)."""
        ms = MemoryStrength(memory_key="test", stability=1.0)

        # Short time (1 min): FSRS < Ebbinghaus (faster initial decay due to factor=19)
        r_fsrs = ms.compute_recall(1.0 / 60.0)  # 1 minute
        r_ebbinghaus = math.exp(-(1.0 / 60.0) / (1.0 * 24))
        assert r_fsrs < r_ebbinghaus, (
            f"FSRS should be lower at 1min: {r_fsrs} vs {r_ebbinghaus}"
        )

        # Long time (100 days): FSRS > Ebbinghaus (power-law tail, Ebbinghaus near-zero)
        r_fsrs = ms.compute_recall(100 * 24.0)
        r_ebbinghaus = math.exp(-(100 * 24.0) / (1.0 * 24))
        assert r_fsrs > r_ebbinghaus, (
            f"FSRS should be higher at 100 days: {r_fsrs} vs {r_ebbinghaus}"
        )

    def test_elapsed_zero_returns_one(self):
        """elapsed_hours=0 → R ≈ 1.0 (backward compat)."""
        ms = MemoryStrength(memory_key="test", stability=5.0)
        assert ms.compute_recall(0.0) == pytest.approx(1.0, abs=1e-6)
