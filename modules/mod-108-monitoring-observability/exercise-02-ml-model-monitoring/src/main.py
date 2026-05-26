"""
ML Model Monitoring — CLI

Subcommands:
    demo            Synthetic deployment monitored across windows;
                    prints health reports + auto-rollback decision.
    ab              Drive two model versions through an A/B test.
"""

from __future__ import annotations

import json
import logging
import random
import sys
from typing import Optional

import click

from .metrics import Prediction
from .model_monitor import ModelMonitor, MonitorConfig


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _stream_predictions(
    monitor: ModelMonitor,
    *,
    model_id: str,
    version: str,
    count: int,
    accuracy: float,
    latency_p95_ms: float,
    seed: int = 42,
    positive_rate: float = 0.3,
) -> None:
    rng = random.Random(seed)
    for _ in range(count):
        label = 1 if rng.random() < positive_rate else 0
        predicted_correct = rng.random() < accuracy
        prediction = label if predicted_correct else 1 - label
        # Latency around a slow-tail distribution: 5% > p95_ms, rest below.
        if rng.random() < 0.05:
            latency = latency_p95_ms * rng.uniform(1.0, 2.0)
        else:
            latency = latency_p95_ms * rng.uniform(0.3, 0.9)
        segment = rng.choice(["us", "eu", "apac"])
        monitor.record(Prediction(
            model=model_id, model_version=version,
            prediction=prediction, score=rng.random(),
            label=label, latency_ms=round(latency, 2),
            segment=segment,
        ))


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """ML model monitor."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--samples-per-window", default=200, type=int)
@click.option("--windows", default=5, type=int)
@click.option("--starting-accuracy", default=0.95, type=float)
@click.option("--accuracy-drop-per-window", default=0.05, type=float)
def demo(
    samples_per_window: int,
    windows: int,
    starting_accuracy: float,
    accuracy_drop_per_window: float,
) -> None:
    """Stream a degrading model through N windows + try rollback."""
    monitor = ModelMonitor(MonitorConfig(
        min_accuracy_for_healthy=0.90,
        min_accuracy_for_degraded=0.80,
        rollback_after_unhealthy_windows=2,
        require_min_samples=samples_per_window // 2,
    ))
    monitor.register_deployment(
        model_id="fraud-detector",
        primary_version="v3.2",
        previous_version="v3.1",
    )
    for w in range(windows):
        accuracy = max(0.55, starting_accuracy - accuracy_drop_per_window * w)
        # Latency creeps up too.
        latency_p95 = 100.0 + w * 80.0
        _stream_predictions(
            monitor,
            model_id="fraud-detector",
            version=monitor._deployments["fraud-detector"].primary_version,
            count=samples_per_window,
            accuracy=accuracy,
            latency_p95_ms=latency_p95,
            seed=w,
        )
        report = monitor.evaluate("fraud-detector")
        click.echo(
            f"window={w} version={report.version}  "
            f"accuracy={report.classification.accuracy:.4f}  "
            f"p95={report.latency.p95_ms:.1f}ms  "
            f"state={report.state.value}"
        )
        for reason in report.reasons:
            click.echo(f"    · {reason}")
        decision = monitor.maybe_rollback("fraud-detector")
        if decision.rolled_back:
            click.echo(
                f"  >>> ROLLBACK: {decision.from_version} → {decision.to_version}  "
                f"({decision.reason})"
            )
            break


@cli.command()
@click.option("--samples", default=300, type=int)
def ab(samples: int) -> None:
    """Run an A/B test with synthetic data on two versions."""
    monitor = ModelMonitor()
    monitor.register_deployment(
        model_id="fraud-detector",
        primary_version="v3.2",
        previous_version="v3.1",
    )
    monitor.start_ab_test("fraud-detector", candidate_version="v3.3",
                           traffic_percent=25.0)
    _stream_predictions(
        monitor, model_id="fraud-detector", version="v3.2",
        count=samples, accuracy=0.90, latency_p95_ms=120.0, seed=1,
    )
    _stream_predictions(
        monitor, model_id="fraud-detector", version="v3.3",
        count=samples, accuracy=0.94, latency_p95_ms=110.0, seed=2,
    )
    decision = monitor.ab_evaluate("fraud-detector")
    if decision is None:
        click.echo("Not enough samples to decide.")
        sys.exit(1)
    click.echo(
        f"Primary v3.2: accuracy={decision.primary_metrics.accuracy:.4f}  "
        f"recall={decision.primary_metrics.recall:.4f}"
    )
    click.echo(
        f"Candidate v3.3: accuracy={decision.candidate_metrics.accuracy:.4f}  "
        f"recall={decision.candidate_metrics.recall:.4f}"
    )
    click.echo(f"Decision: {'PROMOTE' if decision.promote else 'HOLD'} ({decision.reason})")
    if decision.promote:
        state = monitor.promote_candidate("fraud-detector")
        click.echo(f"  primary is now {state.primary_version}; "
                   f"previous = {state.previous_version}")


if __name__ == "__main__":
    cli()
