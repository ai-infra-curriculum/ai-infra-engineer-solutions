"""
Observability Stack — CLI

Subcommands:
    demo        Run a synthetic service for N seconds, instrument it,
                and print the Prometheus exposition + SLO snapshot.
    expose      Print the exposition output for a small canned scenario.
    slo         Compute SLO status from synthetic request stats.
"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
from typing import Optional

import click

from .metrics_exporter import (
    MetricsRegistry,
    SLO,
    SLOTracker,
    StructuredLogger,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Observability stack."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def _instrument_synthetic_service(
    registry: MetricsRegistry,
    slo_tracker: SLOTracker,
    *,
    request_count: int,
    error_rate: float,
    rng: random.Random,
) -> StructuredLogger:
    """Drive a synthetic service and record metrics + structured logs."""
    request_counter = registry.counter(
        "http_requests_total", "HTTP request count",
        label_names=["method", "status_code"],
    )
    latency_histogram = registry.histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        label_names=["method", "route"],
    )
    in_flight = registry.gauge(
        "http_in_flight_requests", "Currently-in-flight requests",
    )
    structured = StructuredLogger("inference-api")

    for _ in range(request_count):
        in_flight.inc()
        is_error = rng.random() < error_rate
        status = "500" if is_error else "200"
        method = rng.choice(["GET", "POST"])
        route = rng.choice(["/predict", "/healthz", "/v1/models/fraud"])
        latency = max(0.001, rng.gauss(0.12, 0.05))
        request_counter.inc(labels={"method": method, "status_code": status})
        latency_histogram.observe(latency, labels={"method": method, "route": route})
        slo_tracker.record(success=not is_error, latency_ms=latency * 1000.0)
        structured.log(
            "ERROR" if is_error else "INFO",
            "request",
            method=method, route=route,
            status_code=int(status), latency_ms=round(latency * 1000.0, 2),
        )
        in_flight.dec()
    return structured


@cli.command()
@click.option("--requests", default=200, type=int)
@click.option("--error-rate", default=0.01, type=float)
@click.option("--seed", default=42, type=int)
def demo(requests: int, error_rate: float, seed: int) -> None:
    """Drive a synthetic service end-to-end and print metrics + SLO."""
    rng = random.Random(seed)
    registry = MetricsRegistry()
    slo = SLO(name="inference-api availability",
              target_availability=0.995,
              target_latency_p95_ms=300.0)
    tracker = SLOTracker(slo)
    structured = _instrument_synthetic_service(
        registry, tracker,
        request_count=requests, error_rate=error_rate, rng=rng,
    )

    click.echo("=== Prometheus /metrics ===\n")
    click.echo(registry.expose())

    click.echo("\n=== SLO Snapshot ===")
    snap = tracker.snapshot()
    click.echo(f"  availability: {snap.observed_availability:.6f} "
               f"(target {snap.slo.target_availability:.4f})")
    click.echo(f"  p95 latency:  {snap.observed_p95_latency_ms}ms "
               f"(target {snap.slo.target_latency_p95_ms}ms)")
    click.echo(f"  error budget remaining: {snap.error_budget_remaining_percent:.2f}%")
    click.echo(f"  burn rate: {snap.burn_rate:.2f}x")
    click.echo(f"  BREACHED" if snap.breached else "  ok")

    click.echo("\n=== Sample structured logs (last 3) ===")
    for record in structured.records[-3:]:
        click.echo(record.to_json())


@cli.command()
def expose() -> None:
    """Print exposition output for a simple canned set of metrics."""
    registry = MetricsRegistry()
    counter = registry.counter("requests_total", "Total requests",
                                label_names=["service"])
    counter.inc(42, labels={"service": "api"})
    counter.inc(7, labels={"service": "worker"})
    histogram = registry.histogram("op_duration_seconds", "Operation duration")
    for v in [0.005, 0.012, 0.045, 0.18, 0.4, 0.9, 1.4, 3.1]:
        histogram.observe(v)
    click.echo(registry.expose())


@cli.command()
@click.option("--errors", default=10, type=int)
@click.option("--total", default=1000, type=int)
@click.option("--target", default=0.999, type=float)
def slo(errors: int, total: int, target: float) -> None:
    """Print the SLO snapshot for a fixed error + total count."""
    tracker = SLOTracker(SLO(name="demo", target_availability=target))
    for i in range(total):
        tracker.record(success=i >= errors, latency_ms=100.0)
    snap = tracker.snapshot()
    click.echo(json.dumps({
        "availability": snap.observed_availability,
        "error_budget_remaining_percent": snap.error_budget_remaining_percent,
        "burn_rate": snap.burn_rate,
        "breached": snap.breached,
    }, indent=2))


if __name__ == "__main__":
    cli()
