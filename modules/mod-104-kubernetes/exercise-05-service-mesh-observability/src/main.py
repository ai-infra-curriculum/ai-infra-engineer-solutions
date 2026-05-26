"""
Service Mesh Observability — CLI Entry Point

Subcommands:
    demo        Run a synthetic 4-service request flow, end-to-end traced,
                and print the resulting golden signals + dependency map +
                SLO compliance.
    canary      Compare baseline vs candidate observations and recommend
                promote / rollback.
"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import List

import click

from .metrics_collector import (
    CanaryEvaluator,
    CanaryRollout,
    DependencyGraph,
    GoldenSignalsCollector,
    RequestObservation,
    SLO,
    SLOEvaluator,
)
from .tracer import (
    InMemoryExporter,
    SpanKind,
    SpanStatus,
    Tracer,
    build_trace_tree,
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
    """Service mesh observability."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--requests", default=200, type=int)
@click.option("--error-rate", default=0.02, type=float, show_default=True)
@click.option("--seed", default=42, type=int)
def demo(requests: int, error_rate: float, seed: int) -> None:
    """Trace a synthetic 4-service flow and print observability output."""
    rng = random.Random(seed)
    exporter = InMemoryExporter()

    gateway = Tracer("api-gateway", exporter=exporter)
    features = Tracer("feature-service", exporter=exporter)
    inference = Tracer("model-inference", exporter=exporter)
    postproc = Tracer("post-processor", exporter=exporter)

    base_time = time.time_ns()
    for i in range(requests):
        status_code = 500 if rng.random() < error_rate else 200
        # Stagger requests over a synthetic 60-second window.
        offset_ns = int(i * (60_000 / max(requests, 1)) * 1_000_000)
        _trace_one_request(
            gateway, features, inference, postproc,
            status_code=status_code,
            rng=rng,
            base_time=base_time + offset_ns,
        )

    for tracer in (gateway, features, inference, postproc):
        tracer.flush()

    # Golden signals.
    collector = GoldenSignalsCollector(window_seconds=300)
    collector.ingest_spans(exporter.spans)
    services = sorted({s.service for s in exporter.spans})
    click.echo("Golden Signals:")
    click.echo(f"  {'Service':<20s} {'RPS':>6s} {'Err%':>6s} {'p50':>6s} {'p95':>6s} {'p99':>6s}")
    for service in services:
        signals = collector.compute(service)
        click.echo(
            f"  {service:<20s} "
            f"{signals.request_rate_per_second:>6.2f} "
            f"{signals.error_rate_percent:>6.2f} "
            f"{signals.p50_latency_ms:>6.1f} "
            f"{signals.p95_latency_ms:>6.1f} "
            f"{signals.p99_latency_ms:>6.1f}"
        )

    # Dependency graph.
    graph = DependencyGraph()
    graph.ingest(exporter)
    click.echo("\nService Dependencies (upstream → downstream):")
    for edge in graph.edges():
        click.echo(
            f"  {edge.upstream:<20s} → {edge.downstream:<20s}  "
            f"calls={edge.request_count:<5d}  "
            f"err%={edge.error_rate_percent:>5.2f}  "
            f"p95={edge.p95_latency_ms:>5.1f}ms"
        )

    # SLO compliance.
    slos = [
        SLO(name="gateway availability", service="api-gateway",
            availability_target=0.99, latency_target_ms=200),
        SLO(name="inference latency", service="model-inference",
            availability_target=0.999, latency_target_ms=150),
    ]
    observations = [
        RequestObservation(
            service=s.service,
            route=s.name,
            duration_ms=s.duration_ms,
            status_code=int(s.attributes.get("http.status_code", 200)),
            timestamp=datetime.fromtimestamp(s.start_ns / 1_000_000_000, tz=timezone.utc),
        )
        for s in exporter.spans
    ]
    click.echo("\nSLO Compliance:")
    for status in SLOEvaluator(slos).evaluate(observations):
        marker = "BREACH" if status.breach else "ok"
        click.echo(
            f"  [{marker}] {status.slo.name}: "
            f"availability={status.observed_availability:.4f} "
            f"(target {status.slo.availability_target:.3f}) "
            f"p95={status.observed_p95_ms:.1f}ms "
            f"(target {status.slo.latency_target_ms:.0f}ms) "
            f"budget consumed={status.error_budget_consumed:.0%}"
        )


@cli.command()
@click.option("--baseline-errors", default=10, type=int,
              help="Number of errors in baseline sample (out of --baseline-total)")
@click.option("--baseline-total", default=1000, type=int)
@click.option("--candidate-errors", default=20, type=int)
@click.option("--candidate-total", default=200, type=int)
@click.option("--baseline-p95", default=120.0, type=float)
@click.option("--candidate-p95", default=180.0, type=float)
def canary(
    baseline_errors: int,
    baseline_total: int,
    candidate_errors: int,
    candidate_total: int,
    baseline_p95: float,
    candidate_p95: float,
) -> None:
    """Decide whether to promote or rollback a candidate version."""
    rng = random.Random(7)
    baseline = _fake_observations("api-gateway", baseline_total, baseline_errors, baseline_p95, rng)
    candidate = _fake_observations("api-gateway", candidate_total, candidate_errors, candidate_p95, rng)
    rollout = CanaryRollout(
        service="api-gateway",
        baseline_version="v1.0",
        candidate_version="v1.1",
        candidate_weight_percent=25.0,
    )
    decision = CanaryEvaluator().decide(rollout, baseline, candidate)
    verdict = "ROLLBACK" if decision.rollback else "PROMOTE"
    click.echo(f"Canary decision: {verdict}")
    click.echo(
        f"  baseline:   err={decision.baseline_error_rate:.2f}%  "
        f"p95={decision.baseline_p95:.1f}ms"
    )
    click.echo(
        f"  candidate:  err={decision.candidate_error_rate:.2f}%  "
        f"p95={decision.candidate_p95:.1f}ms"
    )
    click.echo(f"  rationale:  {decision.rationale}")
    sys.exit(2 if decision.rollback else 0)


def _trace_one_request(gateway, features, inference, postproc, *, status_code, rng, base_time):
    """Emit spans for a four-service flow with controllable latency + status."""
    # Override clock so each request lives at a deterministic timestamp.
    clock_offset = [0]

    def stepping_clock() -> int:
        clock_offset[0] += rng.randint(2_000_000, 10_000_000)  # 2-10ms per step
        return base_time + clock_offset[0]

    for tracer in (gateway, features, inference, postproc):
        tracer.clock = stepping_clock

    root = gateway.start_span("POST /predict", kind=SpanKind.SERVER)
    root.set_attribute("http.status_code", status_code)

    feat = features.start_span("GET /features", kind=SpanKind.SERVER, parent=root)
    features.end_span(feat)

    inf = inference.start_span("infer", kind=SpanKind.SERVER, parent=root)
    inf.set_attribute("http.status_code", status_code)
    if status_code != 200:
        inf.status = SpanStatus.ERROR
    inference.end_span(inf, status=SpanStatus.ERROR if status_code != 200 else None)

    post = postproc.start_span("postprocess", kind=SpanKind.SERVER, parent=root)
    postproc.end_span(post)

    gateway.end_span(root, status=SpanStatus.ERROR if status_code != 200 else None)


def _fake_observations(
    service: str,
    total: int,
    errors: int,
    p95: float,
    rng: random.Random,
) -> List[RequestObservation]:
    obs: List[RequestObservation] = []
    now = datetime.now(timezone.utc)
    for i in range(total):
        is_error = i < errors
        # Generate latencies clustered so that ~5% are at or above p95.
        if rng.random() < 0.05:
            duration = p95 * rng.uniform(1.0, 1.5)
        else:
            duration = p95 * rng.uniform(0.4, 0.9)
        obs.append(RequestObservation(
            service=service,
            route="/predict",
            duration_ms=duration,
            status_code=500 if is_error else 200,
            timestamp=now - timedelta(seconds=i),
        ))
    return obs


if __name__ == "__main__":
    cli()
