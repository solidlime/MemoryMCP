from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from memory_mcp.domain.shared.time_utils import get_now

if TYPE_CHECKING:
    from memory_mcp.application.use_cases import AppContext


class DecayWorker:
    """Ebbinghaus forgetting curve decay worker."""

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

            new_strength_val = strength.compute_recall(elapsed)
            if new_strength_val < self.context.settings.forgetting.min_strength:
                continue

            strength.strength = new_strength_val
            strength.last_decay = now
            self.context.memory_repo.save_strength(strength)
