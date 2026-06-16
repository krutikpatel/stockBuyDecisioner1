from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class RateLimiterStats:
    throttle_events: int = 0


class TokenBucket:
    """Thread-safe token-bucket rate limiter.

    Tokens refill at `rate_per_second` up to `capacity`.
    `acquire()` blocks until a token is available.
    """

    def __init__(self, capacity: float, rate_per_second: float) -> None:
        if capacity <= 0 or rate_per_second <= 0:
            raise ValueError("capacity and rate_per_second must be positive")
        self._capacity = float(capacity)
        self._rate = float(rate_per_second)
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
        self.stats = RateLimiterStats()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def acquire(self, timeout: float | None = None) -> None:
        """Block until a token is available or timeout elapses.

        Raises TimeoutError if timeout is set and no token becomes available.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        throttled = False
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    if throttled:
                        self.stats.throttle_events += 1
                    return
                throttled = True
                wait = (1.0 - self._tokens) / self._rate

            if deadline is not None and time.monotonic() + wait > deadline:
                raise TimeoutError("Rate limiter token not available within timeout")
            time.sleep(min(wait, 0.05))
