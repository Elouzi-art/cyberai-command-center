from __future__ import annotations

import time
from collections import defaultdict


class LoginLimiter:
    """Limiteur en mémoire (un processus). Store partagé requis en multi-instance."""

    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._fails: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self._window
        self._fails[key] = [t for t in self._fails[key] if t > cutoff]
        return self._fails[key]

    def blocked(self, key: str) -> bool:
        return len(self._prune(key)) >= self._max

    def fail(self, key: str) -> None:
        self._prune(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)
