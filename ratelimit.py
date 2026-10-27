"""Rate limit: a per-user ceiling on the expensive photo seam.

In-memory by design (same trade-off as PendingEntries): a restart resets
counters, which at worst briefly under-blocks. The clock is injectable
so tests never sleep.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Callable

_HOUR = timedelta(hours=1)
_MINUTE = timedelta(minutes=1)


class RateLimiter:
    """Sliding-window limiter: an hourly ceiling plus a short burst cap."""

    def __init__(
        self,
        clock: Callable[[], datetime] = datetime.now,
        hourly_limit: int = 10,
        burst_limit: int = 3,
    ) -> None:
        self._clock = clock
        self._hourly_limit = hourly_limit
        self._burst_limit = burst_limit
        self._hourly: dict[int, deque[datetime]] = defaultdict(deque)
        self._burst: dict[int, deque[datetime]] = defaultdict(deque)

    def check(self, user_id: int) -> tuple[bool, timedelta]:
        """Decide whether one more photo is allowed now.

        Returns (allowed, retry_after); a denied call is not counted.
        """
        now = self._clock()
        hourly, burst = self._hourly[user_id], self._burst[user_id]
        self._prune(hourly, now, _HOUR)
        self._prune(burst, now, _MINUTE)

        denied: timedelta | None = None
        if len(hourly) >= self._hourly_limit:
            denied = _HOUR - (now - hourly[0])
        elif len(burst) >= self._burst_limit:
            denied = _MINUTE - (now - burst[0])
        if denied is not None:
            return False, denied

        hourly.append(now)
        burst.append(now)
        return True, timedelta(0)

    @staticmethod
    def _prune(window: deque[datetime], now: datetime, span: timedelta) -> None:
        while window and now - window[0] >= span:
            window.popleft()
