"""Concurrent + throughput tests for the LLM API gateway.

These complement test_api.py's unit-level coverage by hammering the
gateway with realistic mixed-traffic patterns and asserting
end-to-end properties (no leaked in_flight counts, cache hit rate
under repeated traffic, load spreading across backends).
"""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.api_gateway import (
    APIGateway,
    Backend,
    CompletionRequest,
    FakeBackendCaller,
    LLMRouter,
    LoadBalancingStrategy,
    RateLimitConfig,
    ResponseCache,
    RoutingError,
)


def _build_gateway() -> APIGateway:
    backends = [
        Backend(
            backend_id="a", base_url="http://a", supported_models=["m1", "m2"],
            max_concurrent_requests=32, weight=2,
        ),
        Backend(
            backend_id="b", base_url="http://b", supported_models=["m1", "m3"],
            max_concurrent_requests=16, weight=1,
        ),
        Backend(
            backend_id="c", base_url="http://c", supported_models=["m2", "m3"],
            max_concurrent_requests=16, weight=1,
        ),
    ]
    return APIGateway(
        router=LLMRouter(backends, strategy=LoadBalancingStrategy.LEAST_LOADED),
        cache=ResponseCache(max_entries=512, ttl_seconds=600),
        caller=FakeBackendCaller(),
    )


class TestLoad:
    def test_high_volume_no_in_flight_leak(self):
        gateway = _build_gateway()
        rng = random.Random(1)
        models = ["m1", "m2", "m3"]
        for i in range(500):
            try:
                gateway.complete(CompletionRequest(
                    model=rng.choice(models),
                    prompt=f"prompt-{i % 100}",
                    temperature=0.0,
                    max_tokens=10,
                ))
            except RoutingError:
                pass
        # After serial calls finish, in_flight on every backend should be 0.
        for backend in gateway.router.backends.values():
            assert backend.in_flight == 0, (
                f"{backend.backend_id} has lingering in_flight={backend.in_flight}"
            )

    def test_cache_amortization_under_skewed_traffic(self):
        gateway = _build_gateway()
        rng = random.Random(2)
        # 80% of traffic hits 5 popular prompts; 20% varies.
        for _ in range(400):
            if rng.random() < 0.8:
                prompt = f"popular-{rng.randint(1, 5)}"
            else:
                prompt = f"unique-{rng.random()}"
            try:
                gateway.complete(CompletionRequest(
                    model="m1", prompt=prompt, temperature=0.0, max_tokens=10,
                ))
            except RoutingError:
                pass
        # Skewed traffic ⇒ cache hit rate should beat 40%.
        assert gateway.stats.cache_hit_rate_percent > 40.0

    def test_load_distributed_across_backends(self):
        # Force round-robin so the load splits regardless of the
        # least-loaded tie-break favoring early-inserted backends when
        # in_flight settles back to zero between calls.
        from src.api_gateway import (
            Backend, FakeBackendCaller, LLMRouter, LoadBalancingStrategy,
            ResponseCache,
        )
        backends = [
            Backend(backend_id=name, base_url=f"http://{name}",
                    supported_models=["m1", "m2", "m3"],
                    max_concurrent_requests=32)
            for name in ("a", "b", "c")
        ]
        gateway = APIGateway(
            router=LLMRouter(backends, strategy=LoadBalancingStrategy.ROUND_ROBIN),
            cache=ResponseCache(max_entries=512),
            caller=FakeBackendCaller(),
        )
        rng = random.Random(3)
        for i in range(300):
            try:
                gateway.complete(CompletionRequest(
                    model=rng.choice(["m1", "m2", "m3"]),
                    prompt=f"distinct-{i}",  # avoid cache
                    temperature=0.7,
                    max_tokens=10,
                ))
            except RoutingError:
                pass
        for backend in gateway.router.backends.values():
            assert backend.request_count > 0

    def test_concurrent_requests_safe(self):
        gateway = _build_gateway()

        def _run(i: int) -> bool:
            try:
                gateway.complete(CompletionRequest(
                    model="m1", prompt=f"p-{i}", temperature=0.0, max_tokens=10,
                ))
                return True
            except RoutingError:
                return False

        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(_run, range(200)))
        # No exception leaked; every backend ends with in_flight == 0.
        assert any(results)
        for backend in gateway.router.backends.values():
            assert backend.in_flight == 0


class TestRateLimitUnderLoad:
    def test_rate_limit_rejects_burst_excess(self):
        backends = [Backend(
            backend_id="solo", base_url="http://solo",
            supported_models=["m1"], max_concurrent_requests=32,
        )]
        gateway = APIGateway(
            router=LLMRouter(
                backends,
                rate_limits={"m1": RateLimitConfig(requests_per_second=2, burst=5)},
            ),
            cache=ResponseCache(),
            caller=FakeBackendCaller(),
        )
        accepted = rejected = 0
        for i in range(30):
            try:
                gateway.complete(CompletionRequest(
                    model="m1", prompt=f"p-{i}", temperature=0.7, max_tokens=10,
                ))
                accepted += 1
            except RoutingError:
                rejected += 1
        # Rate limit (burst=5, rps=2) ⇒ at most ~5 requests in the
        # first instant should land before rejections begin.
        assert rejected > 0
        assert accepted < 30


class TestFailoverUnderLoad:
    def test_backend_failure_failover(self):
        # Single-backend setup so all failures concentrate on it; with
        # multiple backends the LEAST_LOADED strategy spreads failures
        # by (in_flight, error_count) tie-break, which is the desired
        # production behavior — to test failover we need to force the
        # consecutive_failures threshold deterministically.
        from src.api_gateway import (
            Backend, FakeBackendCaller, LLMRouter, ResponseCache,
        )
        primary = Backend(
            backend_id="primary", base_url="http://primary",
            supported_models=["m1"], max_concurrent_requests=4, weight=10,
        )
        backup = Backend(
            backend_id="backup", base_url="http://backup",
            supported_models=["m1"], max_concurrent_requests=4, weight=1,
        )
        # Mark backup unhealthy initially so all calls hit primary.
        router = LLMRouter([primary, backup])
        router.force_health("backup", False)
        caller = FakeBackendCaller()
        caller.fail_next_n_calls = 3
        gateway = APIGateway(
            router=router, cache=ResponseCache(), caller=caller,
        )
        for _ in range(3):
            try:
                gateway.complete(CompletionRequest(
                    model="m1", prompt="x", temperature=0.7, max_tokens=10,
                ))
            except RuntimeError:
                pass
        assert not router.backends["primary"].healthy
        # Now restore backup; subsequent calls should route to it.
        router.force_health("backup", True)
        response = gateway.complete(CompletionRequest(
            model="m1", prompt="after-failover", temperature=0.7, max_tokens=10,
        ))
        assert response.backend_id == "backup"
