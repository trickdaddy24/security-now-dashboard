from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    reset_seconds: float = 300.0
    _failures: int = 0
    _opened_at: float | None = None

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.time()

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.time() - self._opened_at >= self.reset_seconds:
            self._failures = 0
            self._opened_at = None
            return False
        return True

    def status(self) -> dict[str, float | int | bool | None]:
        return {
            "open": self.is_open(),
            "failures": self._failures,
            "opened_at": self._opened_at,
        }