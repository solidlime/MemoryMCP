from __future__ import annotations

import contextlib
import threading
import time
from typing import TYPE_CHECKING

from nous.domain.shared.time_utils import get_now

if TYPE_CHECKING:
    from nous.application.use_cases import AppContext


class DecayWorker:
    """FSRS v6 power-law forgetting curve decay worker."""

    def __init__(self, context: AppContext, interval_seconds: int = 3600) -> None:
        self.context = context
        self.interval = interval_seconds
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        while self._running:
            self._decay_cycle()
            time.sleep(self.interval)

    def _decay_cycle(self) -> None:
        """Run one decay cycle: update all memory strengths."""
        result = self.context.memory_repo.get_all_strengths()
        if not result.is_ok:
            return

        now = get_now()
        for strength in result.value:
            elapsed = (now - strength.last_decay).total_seconds() / 3600 if strength.last_decay else 24.0

            # LTM uses slower decay exponent
            decay_exp = 0.3 if strength.is_ltm else 0.5
            recall = strength.compute_recall(elapsed, decay_exponent=decay_exp)
            score = strength.compute_strength_score()
            new_strength_val = recall * score

            # STM → LTM automatic promotion (before min_strength check)
            if not strength.is_ltm and new_strength_val > 0.7 and strength.recall_count >= 3:
                strength.is_ltm = True

            # Archive condition (before min_strength check)
            if new_strength_val < 0.2 and strength.last_recall:
                # Unify timezone to avoid aware/naive mismatch
                _now = now.replace(tzinfo=None)
                _last = strength.last_recall.replace(tzinfo=None)
                inactive_days = (_now - _last).days
                if inactive_days > 30:
                    with contextlib.suppress(Exception):
                        self.context.memory_repo.update(
                            strength.memory_key,
                            lifecycle_status="archived",
                        )

            if new_strength_val < self.context.settings.forgetting.min_strength:
                continue

            strength.strength = new_strength_val
            strength.last_decay = now
            self.context.memory_repo.save_strength(strength)
