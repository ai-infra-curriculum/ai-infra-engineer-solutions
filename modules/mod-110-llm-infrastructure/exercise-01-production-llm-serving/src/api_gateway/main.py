"""
LLM API Gateway Orchestrator

Composes the cache + router + a pluggable backend caller into one
end-to-end completion pipeline. The caller is a Protocol so production
deployments swap in an HTTP client against real vLLM endpoints; tests
use the in-memory FakeBackendCaller.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Protocol

from .cache import ResponseCache
from .router import (
    Backend,
    LLMRouter,
    RoutingDecision,
    RoutingError,
    TokenUsage,
    estimate_token_count,
)


logger = logging.getLogger(__name__)


@dataclass
class CompletionRequest:
    """OpenAI-compatible request shape."""

    model: str
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 256
    user_id: Optional[str] = None


@dataclass
class CompletionResponse:
    """OpenAI-compatible response shape."""

    request_id: str
    model: str
    text: str
    prompt_tokens: int
    completion_tokens: int
    backend_id: str
    cache_hit: bool
    latency_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class BackendCaller(Protocol):
    """Pluggable client that hits a vLLM backend."""

    def invoke(self, decision: RoutingDecision, request: CompletionRequest) -> str: ...


class FakeBackendCaller:
    """Deterministic in-memory caller used in tests + CLI demos."""

    def __init__(self):
        self.calls: List[CompletionRequest] = []
        self.fail_next_n_calls: int = 0
        self.latency_ms: float = 25.0

    def invoke(self, decision: RoutingDecision, request: CompletionRequest) -> str:
        if self.fail_next_n_calls > 0:
            self.fail_next_n_calls -= 1
            raise RuntimeError(f"Synthetic backend failure for {decision.backend.backend_id}")
        self.calls.append(request)
        # Simulate latency without actually sleeping (so tests stay fast).
        return f"[{request.model}@{decision.backend.backend_id}] {request.prompt[:40]}"


@dataclass
class GatewayStats:
    """Cross-request gateway counters."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    backend_errors: int = 0
    routing_errors: int = 0

    @property
    def cache_hit_rate_percent(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100.0) if total else 0.0


class APIGateway:
    """Cache + router + caller pipeline."""

    def __init__(
        self,
        router: LLMRouter,
        cache: ResponseCache,
        caller: BackendCaller,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.router = router
        self.cache = cache
        self.caller = caller
        self.clock = clock
        self.stats = GatewayStats()
        self.usage_by_model: Dict[str, TokenUsage] = {}

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """End-to-end completion path: cache → route → call → record."""
        self.stats.total_requests += 1
        started = time.perf_counter()
        cached = self.cache.get(
            model=request.model, prompt=request.prompt,
            temperature=request.temperature, max_tokens=request.max_tokens,
            user_id=request.user_id,
        )
        if cached is not None:
            self.stats.cache_hits += 1
            latency = (time.perf_counter() - started) * 1000.0
            return CompletionResponse(
                request_id="cache-hit",
                model=request.model,
                text=cached,
                prompt_tokens=estimate_token_count(request.prompt),
                completion_tokens=estimate_token_count(cached),
                backend_id="cache",
                cache_hit=True,
                latency_ms=round(latency, 2),
                timestamp=self.clock(),
            )
        self.stats.cache_misses += 1

        try:
            decision = self.router.route(model=request.model, user_id=request.user_id)
        except RoutingError:
            self.stats.routing_errors += 1
            raise

        backend_id = decision.backend.backend_id
        try:
            text = self.caller.invoke(decision, request)
            self.router.report_success(backend_id)
        except Exception as exc:
            self.router.report_failure(backend_id)
            self.stats.backend_errors += 1
            raise

        prompt_tokens = estimate_token_count(request.prompt)
        completion_tokens = estimate_token_count(text)
        usage = self.usage_by_model.setdefault(
            request.model, TokenUsage(model=request.model),
        )
        usage.prompt_tokens += prompt_tokens
        usage.completion_tokens += completion_tokens
        usage.requests += 1

        self.cache.put(
            model=request.model, prompt=request.prompt,
            temperature=request.temperature, max_tokens=request.max_tokens,
            response=text, tokens_used=prompt_tokens + completion_tokens,
            user_id=request.user_id,
        )

        latency = (time.perf_counter() - started) * 1000.0
        return CompletionResponse(
            request_id=decision.request_id,
            model=request.model,
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            backend_id=backend_id,
            cache_hit=False,
            latency_ms=round(latency, 2),
            timestamp=self.clock(),
        )
