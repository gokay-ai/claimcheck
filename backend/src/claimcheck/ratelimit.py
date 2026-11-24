"""Request limits for a public demo that spends from a single model key."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

DAY_SECONDS = 86_400


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_seconds: int = 0


class RateLimiter:
    """A sliding window per client and a daily cap across all clients.

    State is held in memory: one process serves the demo, and losing the
    counters on restart only makes the limit briefly more generous.
    """

    def __init__(
        self,
        *,
        per_client: int,
        window_seconds: int,
        daily_cap: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._per_client = per_client
        self._window = window_seconds
        self._daily_cap = daily_cap
        self._clock = clock
        self._by_client: dict[str, deque[float]] = defaultdict(deque)
        self._all: deque[float] = deque()

    def check(self, client: str) -> Decision:
        now = self._clock()
        recent = self._by_client[client]
        while recent and now - recent[0] >= self._window:
            recent.popleft()
        while self._all and now - self._all[0] >= DAY_SECONDS:
            self._all.popleft()

        if len(self._all) >= self._daily_cap:
            return Decision(False, int(DAY_SECONDS - (now - self._all[0])) + 1)
        if len(recent) >= self._per_client:
            return Decision(False, int(self._window - (now - recent[0])) + 1)

        recent.append(now)
        self._all.append(now)
        return Decision(True)
