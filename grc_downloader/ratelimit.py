from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    def __init__(self, max_per_minute: int = 10):
        self.max_per_minute = max(1, max_per_minute)
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - 60.0
        with self._lock:
            self._hits[key] = [t for t in self._hits[key] if t >= cutoff]
            if len(self._hits[key]) >= self.max_per_minute:
                return False
            self._hits[key].append(now)
            return True