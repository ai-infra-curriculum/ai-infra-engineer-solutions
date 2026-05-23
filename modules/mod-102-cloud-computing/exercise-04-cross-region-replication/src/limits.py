"""Token-bucket rate limiter for bandwidth-throttled transfers."""
from __future__ import annotations

import threading
import time


class TokenBucket:
    """Thread-safe token bucket. Tokens = bytes; rate = bytes/sec."""

    def __init__(self, rate_bytes_per_sec: float, capacity_bytes: float | None = None) -> None:
        self.rate = float(rate_bytes_per_sec)
        self.capacity = float(capacity_bytes or rate_bytes_per_sec)
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, n: int) -> None:
        """Block until `n` tokens are available, then consume them."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                if self._tokens >= n:
                    self._tokens -= n
                    return
                deficit = n - self._tokens
            time.sleep(deficit / self.rate)
