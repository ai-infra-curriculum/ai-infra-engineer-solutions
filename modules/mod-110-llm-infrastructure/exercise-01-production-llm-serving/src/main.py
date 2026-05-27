"""
Production LLM Serving Gateway — CLI

Subcommands:
    demo        Run an end-to-end gateway demo against three synthetic
                vLLM backends with cache + routing + rate limits.
    stats       Same as demo but emits stats only.
"""

from __future__ import annotations

import json
import logging
import random
import sys

import click

from .api_gateway import (
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


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _build_gateway(
    *,
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LOADED,
    rate_limit_rps: float = 200.0,
    cache_capacity: int = 256,
) -> APIGateway:
    backends = [
        Backend(
            backend_id="vllm-pool-a", base_url="http://vllm-a:8000",
            supported_models=["llama2-7b", "mistral-7b"],
            max_concurrent_requests=16, weight=2,
        ),
        Backend(
            backend_id="vllm-pool-b", base_url="http://vllm-b:8000",
            supported_models=["llama2-7b", "codellama-13b"],
            max_concurrent_requests=8, weight=1,
        ),
        Backend(
            backend_id="vllm-pool-c", base_url="http://vllm-c:8000",
            supported_models=["mistral-7b", "codellama-13b"],
            max_concurrent_requests=12, weight=1,
        ),
    ]
    # Demo uses generous bursts so a tight CLI loop doesn't trip the
    # limiter on in-process synchronous calls. Production tuning would
    # use the realistic 5-20 req/s / 10-burst values you see tested in
    # tests/load_test.py::TestRateLimitUnderLoad.
    rate_limits = {
        "llama2-7b": RateLimitConfig(requests_per_second=rate_limit_rps, burst=500),
        "mistral-7b": RateLimitConfig(requests_per_second=rate_limit_rps, burst=500),
        "codellama-13b": RateLimitConfig(
            requests_per_second=rate_limit_rps / 2, burst=200,
        ),
    }
    router = LLMRouter(backends, strategy=strategy, rate_limits=rate_limits)
    cache = ResponseCache(max_entries=cache_capacity, ttl_seconds=300)
    return APIGateway(router=router, cache=cache, caller=FakeBackendCaller())


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Production LLM serving gateway."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--requests", default=50, type=int)
@click.option("--seed", default=42, type=int)
def demo(requests: int, seed: int) -> None:
    """Drive synthetic requests through the gateway."""
    gateway = _build_gateway()
    rng = random.Random(seed)
    prompts = [
        "Summarize the following: ",
        "Translate to French: ",
        "Write Python code that: ",
        "Explain step by step: ",
    ]
    models = ["llama2-7b", "mistral-7b", "codellama-13b"]
    sent = errored = cached = 0
    for i in range(requests):
        try:
            request = CompletionRequest(
                model=rng.choice(models),
                prompt=rng.choice(prompts) + f"item-{rng.randint(1, 20)}",
                temperature=0.0 if rng.random() < 0.5 else 0.7,
                max_tokens=128,
                user_id=f"user-{rng.randint(1, 5):02d}",
            )
            response = gateway.complete(request)
            sent += 1
            if response.cache_hit:
                cached += 1
        except RoutingError as exc:
            errored += 1
            logger.debug("Routing error: %s", exc)
    click.echo(f"Sent: {sent}   Cached: {cached}   Errored: {errored}")
    _print_summary(gateway)


@cli.command()
@click.option("--requests", default=200, type=int)
def stats(requests: int) -> None:
    """Print only the cumulative gateway stats."""
    gateway = _build_gateway()
    rng = random.Random(0)
    for i in range(requests):
        try:
            gateway.complete(CompletionRequest(
                model=rng.choice(["llama2-7b", "mistral-7b"]),
                prompt=f"prompt-{i % 30}",
                temperature=0.0,
                max_tokens=128,
            ))
        except RoutingError:
            pass
    _print_summary(gateway)


def _print_summary(gateway: APIGateway) -> None:
    click.echo("\n=== Gateway stats ===")
    click.echo(f"  total_requests:    {gateway.stats.total_requests}")
    click.echo(f"  cache_hits:        {gateway.stats.cache_hits}")
    click.echo(f"  cache_misses:      {gateway.stats.cache_misses}")
    click.echo(f"  routing_errors:    {gateway.stats.routing_errors}")
    click.echo(f"  backend_errors:    {gateway.stats.backend_errors}")
    click.echo(f"  cache_hit_rate:    {gateway.stats.cache_hit_rate_percent:.1f}%")

    click.echo("\n=== Per-model token usage ===")
    for model, usage in gateway.usage_by_model.items():
        click.echo(
            f"  {model:<16s} requests={usage.requests:<5d} "
            f"prompt_tokens={usage.prompt_tokens:<6d} "
            f"completion_tokens={usage.completion_tokens:<6d} "
            f"total={usage.total_tokens}"
        )

    click.echo("\n=== Backend stats ===")
    for backend in gateway.router.backends.values():
        click.echo(
            f"  {backend.backend_id:<18s} requests={backend.request_count:<5d} "
            f"errors={backend.error_count:<3d} "
            f"in_flight={backend.in_flight:<3d} "
            f"healthy={backend.healthy}"
        )


if __name__ == "__main__":
    cli()
