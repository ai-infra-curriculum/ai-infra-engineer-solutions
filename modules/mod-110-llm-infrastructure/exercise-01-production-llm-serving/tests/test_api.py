"""Tests for the LLM API gateway (cache + router + orchestrator)."""

from datetime import datetime, timedelta, timezone

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
    cache_key,
    estimate_token_count,
)


def _backends(*, count=2) -> list[Backend]:
    return [
        Backend(
            backend_id=f"backend-{i}",
            base_url=f"http://backend-{i}",
            supported_models=["llama2-7b", "mistral-7b"],
            max_concurrent_requests=4, weight=1,
        )
        for i in range(count)
    ]


def _gateway(
    *,
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LOADED,
    rate_limits: dict | None = None,
    cache: ResponseCache | None = None,
) -> tuple[APIGateway, FakeBackendCaller]:
    backends = _backends()
    router = LLMRouter(backends, strategy=strategy, rate_limits=rate_limits or {})
    caller = FakeBackendCaller()
    gateway = APIGateway(
        router=router,
        cache=cache or ResponseCache(max_entries=64, ttl_seconds=3600),
        caller=caller,
    )
    return gateway, caller


class TestResponseCache:
    def test_miss_returns_none(self):
        cache = ResponseCache()
        assert cache.get(model="m", prompt="p", temperature=0.0, max_tokens=10) is None
        assert cache.stats.misses == 1

    def test_put_then_hit(self):
        cache = ResponseCache()
        cache.put(model="m", prompt="p", temperature=0.0, max_tokens=10, response="hello")
        result = cache.get(model="m", prompt="p", temperature=0.0, max_tokens=10)
        assert result == "hello"
        assert cache.stats.hits == 1

    def test_temperature_above_threshold_not_cached(self):
        cache = ResponseCache()
        cache.put(model="m", prompt="p", temperature=0.7, max_tokens=10, response="x")
        assert cache.get(model="m", prompt="p", temperature=0.7, max_tokens=10) is None

    def test_ttl_expiry(self):
        cache = ResponseCache(ttl_seconds=10)
        now = datetime.now(timezone.utc)
        cache.put(model="m", prompt="p", temperature=0.0, max_tokens=10, response="x", now=now)
        # 5 seconds later: still valid.
        assert cache.get(model="m", prompt="p", temperature=0.0, max_tokens=10, now=now + timedelta(seconds=5)) == "x"
        # 30 seconds later: expired.
        assert cache.get(model="m", prompt="p", temperature=0.0, max_tokens=10, now=now + timedelta(seconds=30)) is None

    def test_capacity_evicts_lru(self):
        cache = ResponseCache(max_entries=2)
        for i in range(3):
            cache.put(model="m", prompt=f"p{i}", temperature=0.0, max_tokens=10, response=f"r{i}")
        # 'p0' should be evicted (oldest).
        assert cache.get(model="m", prompt="p0", temperature=0.0, max_tokens=10) is None
        # Newer entries still present.
        assert cache.get(model="m", prompt="p2", temperature=0.0, max_tokens=10) == "r2"

    def test_sweep_expired(self):
        cache = ResponseCache(ttl_seconds=10)
        now = datetime.now(timezone.utc)
        cache.put(model="m", prompt="old", temperature=0.0, max_tokens=10, response="o", now=now - timedelta(seconds=60))
        cache.put(model="m", prompt="new", temperature=0.0, max_tokens=10, response="n", now=now)
        removed = cache.sweep_expired(now=now)
        assert removed == 1

    def test_hit_rate_calculation(self):
        cache = ResponseCache()
        cache.put(model="m", prompt="p", temperature=0.0, max_tokens=10, response="x")
        cache.get(model="m", prompt="p", temperature=0.0, max_tokens=10)
        cache.get(model="m", prompt="other", temperature=0.0, max_tokens=10)
        assert cache.stats.hit_rate_percent == 50.0


class TestLLMRouter:
    def test_requires_backends(self):
        with pytest.raises(ValueError):
            LLMRouter([])

    def test_routes_to_supporting_backend(self):
        router = LLMRouter(_backends())
        decision = router.route(model="llama2-7b")
        assert decision.backend.backend_id.startswith("backend-")

    def test_unsupported_model_fails(self):
        router = LLMRouter(_backends())
        with pytest.raises(RoutingError):
            router.route(model="claude-3")

    def test_unhealthy_backends_skipped(self):
        backends = _backends(count=2)
        router = LLMRouter(backends)
        router.force_health("backend-0", healthy=False)
        decision = router.route(model="llama2-7b")
        assert decision.backend.backend_id == "backend-1"

    def test_failure_threshold_marks_unhealthy(self):
        router = LLMRouter(_backends(count=1))
        for _ in range(router.FAILURE_THRESHOLD):
            router.report_failure("backend-0")
        assert not router.backends["backend-0"].healthy

    def test_least_loaded_picks_lower_in_flight(self):
        backends = _backends(count=2)
        backends[0].in_flight = 3
        router = LLMRouter(backends, strategy=LoadBalancingStrategy.LEAST_LOADED)
        decision = router.route(model="llama2-7b")
        assert decision.backend.backend_id == "backend-1"

    def test_concurrency_limit_skips_full_backends(self):
        backends = _backends(count=2)
        backends[0].in_flight = backends[0].max_concurrent_requests
        router = LLMRouter(backends)
        decision = router.route(model="llama2-7b")
        assert decision.backend.backend_id == "backend-1"

    def test_rate_limit_rejects_excess_requests(self):
        router = LLMRouter(
            _backends(count=1),
            rate_limits={"llama2-7b": RateLimitConfig(requests_per_second=1, burst=2)},
        )
        # Two requests consume the bucket.
        router.route(model="llama2-7b")
        router.route(model="llama2-7b")
        with pytest.raises(RoutingError):
            router.route(model="llama2-7b")

    def test_report_success_resets_failures(self):
        router = LLMRouter(_backends(count=1))
        router.report_failure("backend-0")
        router.report_success("backend-0")
        assert router.backends["backend-0"].consecutive_failures == 0


class TestEstimateTokenCount:
    def test_empty(self):
        assert estimate_token_count("") == 0

    def test_one_word(self):
        # 1 word × 1.3 ≈ 2 tokens after ceil.
        assert estimate_token_count("hello") >= 1

    def test_proportional(self):
        few = estimate_token_count("a b c d e")
        many = estimate_token_count(" ".join(["x"] * 100))
        assert many > few


class TestAPIGateway:
    def test_complete_routes_and_caches(self):
        gateway, caller = _gateway()
        response = gateway.complete(CompletionRequest(
            model="llama2-7b", prompt="hello", temperature=0.0, max_tokens=10,
        ))
        assert not response.cache_hit
        assert response.backend_id.startswith("backend-")
        # Cached on second request.
        again = gateway.complete(CompletionRequest(
            model="llama2-7b", prompt="hello", temperature=0.0, max_tokens=10,
        ))
        assert again.cache_hit
        assert again.text == response.text
        # Caller invoked only for the first request.
        assert len(caller.calls) == 1

    def test_token_usage_recorded(self):
        gateway, _ = _gateway()
        for _ in range(5):
            gateway.complete(CompletionRequest(
                model="llama2-7b", prompt="hello world", temperature=0.7,
                max_tokens=10,
            ))
        usage = gateway.usage_by_model["llama2-7b"]
        assert usage.requests == 5
        assert usage.prompt_tokens > 0
        assert usage.completion_tokens > 0

    def test_routing_error_increments_counter(self):
        gateway, _ = _gateway()
        with pytest.raises(RoutingError):
            gateway.complete(CompletionRequest(
                model="claude-3", prompt="x", temperature=0.0, max_tokens=10,
            ))
        assert gateway.stats.routing_errors == 1

    def test_backend_error_reports_to_router(self):
        gateway, caller = _gateway()
        caller.fail_next_n_calls = 1
        with pytest.raises(RuntimeError):
            gateway.complete(CompletionRequest(
                model="llama2-7b", prompt="hello", temperature=0.0, max_tokens=10,
            ))
        assert gateway.stats.backend_errors == 1
        # The router records the failure on the picked backend.
        any_failures = any(
            b.consecutive_failures > 0 for b in gateway.router.backends.values()
        )
        assert any_failures

    def test_hit_rate_percent_climbs_with_repeated_prompt(self):
        gateway, _ = _gateway()
        for _ in range(10):
            gateway.complete(CompletionRequest(
                model="llama2-7b", prompt="duplicate", temperature=0.0, max_tokens=10,
            ))
        # First miss + 9 hits.
        assert gateway.stats.cache_hit_rate_percent == pytest.approx(90.0)


class TestCacheKey:
    def test_distinct_keys_for_distinct_inputs(self):
        a = cache_key(model="m", prompt="p1", temperature=0.0, max_tokens=10)
        b = cache_key(model="m", prompt="p2", temperature=0.0, max_tokens=10)
        assert a != b

    def test_same_inputs_yield_same_key(self):
        a = cache_key(model="m", prompt="p", temperature=0.0, max_tokens=10, user_id="u1")
        b = cache_key(model="m", prompt="p", temperature=0.0, max_tokens=10, user_id="u1")
        assert a == b
