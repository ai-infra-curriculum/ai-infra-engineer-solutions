"""
LLM Backend Router

Routes inbound requests to one of multiple vLLM backends based on:
- model affinity (different LLMs on different pools)
- pool health (mark backends unhealthy after consecutive failures)
- load-balancing strategy (round-robin / least-loaded / weighted)
- per-model token-bucket rate limits

The router does not perform the HTTP call itself; it returns a
RoutingDecision the caller invokes against. This keeps the routing
logic independent of the HTTP client and trivially unit-testable.
"""

from __future__ import annotations

import itertools
import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Sequence


logger = logging.getLogger(__name__)


class LoadBalancingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    WEIGHTED = "weighted"


@dataclass
class Backend:
    """One vLLM backend pool."""

    backend_id: str
    base_url: str
    supported_models: List[str]
    max_concurrent_requests: int = 16
    weight: int = 1  # for weighted load balancing

    # Mutable runtime state.
    in_flight: int = 0
    consecutive_failures: int = 0
    healthy: bool = True
    request_count: int = 0
    error_count: int = 0


class RoutingError(Exception):
    """Raised when no eligible backend is available."""


@dataclass
class RoutingDecision:
    """Output of one routing call."""

    backend: Backend
    model: str
    request_id: str


@dataclass
class RateLimitConfig:
    """Per-model token-bucket configuration."""

    requests_per_second: float
    burst: int


@dataclass
class _TokenBucket:
    capacity: int
    tokens: float
    refill_rate_per_second: float
    last_refill: datetime

    def try_consume(self, *, amount: float = 1.0, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        elapsed = max(0.0, (now - self.last_refill).total_seconds())
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_second)
        self.last_refill = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class LLMRouter:
    """Backend selection + health + rate limiting."""

    FAILURE_THRESHOLD = 3

    def __init__(
        self,
        backends: Sequence[Backend],
        *,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LOADED,
        rate_limits: Optional[Dict[str, RateLimitConfig]] = None,
    ):
        if not backends:
            raise ValueError("Router requires at least one backend")
        self.backends: Dict[str, Backend] = {b.backend_id: b for b in backends}
        self.strategy = strategy
        self._rate_limits = rate_limits or {}
        self._buckets: Dict[str, _TokenBucket] = {}
        for model, config in self._rate_limits.items():
            self._buckets[model] = _TokenBucket(
                capacity=config.burst, tokens=float(config.burst),
                refill_rate_per_second=config.requests_per_second,
                last_refill=datetime.now(timezone.utc),
            )
        self._round_robin = itertools.cycle(sorted(self.backends))
        self._lock = threading.RLock()
        self._request_counter = 0

    # -- backend health -------------------------------------------------

    def report_success(self, backend_id: str) -> None:
        with self._lock:
            b = self.backends[backend_id]
            b.consecutive_failures = 0
            b.request_count += 1
            b.in_flight = max(0, b.in_flight - 1)
            if not b.healthy:
                b.healthy = True
                logger.info("Backend %s back to healthy", backend_id)

    def report_failure(self, backend_id: str) -> None:
        with self._lock:
            b = self.backends[backend_id]
            b.consecutive_failures += 1
            b.error_count += 1
            b.in_flight = max(0, b.in_flight - 1)
            if b.consecutive_failures >= self.FAILURE_THRESHOLD:
                b.healthy = False
                logger.warning("Backend %s marked unhealthy", backend_id)

    def force_health(self, backend_id: str, healthy: bool) -> None:
        with self._lock:
            self.backends[backend_id].healthy = healthy

    # -- routing --------------------------------------------------------

    def route(
        self,
        *,
        model: str,
        user_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> RoutingDecision:
        with self._lock:
            if model in self._buckets:
                bucket = self._buckets[model]
                if not bucket.try_consume(now=now):
                    raise RoutingError(
                        f"Rate limit exceeded for model {model!r} "
                        f"(rate={self._rate_limits[model].requests_per_second}/sec)"
                    )
            candidates = [
                b for b in self.backends.values()
                if b.healthy and model in b.supported_models
                and b.in_flight < b.max_concurrent_requests
            ]
            if not candidates:
                raise RoutingError(
                    f"No healthy backend with capacity available for {model!r}"
                )
            backend = self._pick(candidates)
            backend.in_flight += 1
            self._request_counter += 1
            return RoutingDecision(
                backend=backend, model=model,
                request_id=f"req-{self._request_counter:08d}",
            )

    def _pick(self, candidates: List[Backend]) -> Backend:
        if self.strategy is LoadBalancingStrategy.ROUND_ROBIN:
            # Walk the cycle until we hit a candidate.
            for _ in range(len(self.backends)):
                candidate_id = next(self._round_robin)
                for c in candidates:
                    if c.backend_id == candidate_id:
                        return c
            return candidates[0]
        if self.strategy is LoadBalancingStrategy.LEAST_LOADED:
            return min(candidates, key=lambda b: (b.in_flight, b.error_count))
        if self.strategy is LoadBalancingStrategy.WEIGHTED:
            # Pick the candidate with the highest weight / (in_flight + 1).
            return max(candidates, key=lambda b: b.weight / (b.in_flight + 1))
        return candidates[0]


# -- Token-counting helpers --------------------------------------------


@dataclass
class TokenUsage:
    """Tracks cumulative token usage for cost attribution."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    requests: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def estimate_token_count(text: str) -> int:
    """Cheap word-count-based token estimate.

    Real implementations call tiktoken/sentencepiece; this approximation
    is sufficient for the gateway's rate-limit + cost-tracking paths
    where the exact tokeniser tracks per-model anyway.
    """
    if not text:
        return 0
    # Roughly 1.3 tokens per word for English; rounds up.
    return max(1, math.ceil(len(text.split()) * 1.3))
