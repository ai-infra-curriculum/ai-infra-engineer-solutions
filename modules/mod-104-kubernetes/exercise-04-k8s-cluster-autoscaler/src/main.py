"""
Kubernetes Cluster Autoscaler — CLI entry point

Subcommands:
    simulate    Run a deterministic simulation across a time window
                using synthetic metrics, printing the decision history.
    decide      Make a single decision against a synthetic metric and
                print the resulting ScalingDecision.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import click

from .autoscaler import Autoscaler, AutoscalerPolicy
from .metrics_collector import (
    LinearForecast,
    MetricsCollector,
    PodMetric,
    WorkloadMetric,
)
from .scaler import (
    InMemoryScalerBackend,
    Scaler,
    ScalingDecision,
    ScaleDirection,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _sine_wave_metric(
    *,
    workload: str,
    namespace: str,
    replica_count: int,
    minutes_elapsed: float,
) -> WorkloadMetric:
    """Synthetic metric with sinusoidal load + GPU-style utilization."""
    phase = math.sin(minutes_elapsed / 30.0 * 2.0 * math.pi) * 0.5 + 0.5
    cpu = 0.3 + phase * 0.6
    gpu = 0.2 + phase * 0.7
    queue = max(0.0, (phase - 0.6) * 60)  # bursts during peaks
    pods = [
        PodMetric(
            pod=f"{workload}-{i}",
            namespace=namespace,
            cpu_utilization=cpu,
            memory_utilization=min(cpu * 0.9, 1.0),
            gpu_utilization=gpu,
        )
        for i in range(replica_count)
    ]
    return WorkloadMetric(
        workload=workload,
        namespace=namespace,
        replica_count=replica_count,
        pod_metrics=pods,
        queue_depth=queue,
        p95_latency_ms=80 + phase * 200,
    )


class _SyntheticCollector(MetricsCollector):
    """Collector that bypasses Prometheus and yields synthetic snapshots."""

    def __init__(self, backend: InMemoryScalerBackend, *, namespace: str, workload: str):
        super().__init__(prometheus_query=lambda q: [])
        self.backend = backend
        self.namespace = namespace
        self.workload = workload
        self._minute = 0

    def collect(self, namespace: str, workload: str) -> WorkloadMetric:
        replicas = self.backend.get_replicas(namespace, workload)
        metric = _sine_wave_metric(
            workload=workload,
            namespace=namespace,
            replica_count=replicas,
            minutes_elapsed=self._minute,
        )
        self._minute += 1
        return metric


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Kubernetes autoscaler."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--workload", default="ml-api")
@click.option("--namespace", default="ml")
@click.option("--initial-replicas", default=3, type=int)
@click.option("--ticks", default=24, type=int)
@click.option("--target-queue-depth", default=10.0, type=float)
@click.option("--scale-up-step", default=2, type=int)
def simulate(
    workload: str,
    namespace: str,
    initial_replicas: int,
    ticks: int,
    target_queue_depth: float,
    scale_up_step: int,
) -> None:
    """Run a deterministic simulation."""
    backend = InMemoryScalerBackend()
    backend.set_replicas(namespace, workload, initial_replicas)
    collector = _SyntheticCollector(backend, namespace=namespace, workload=workload)
    scaler = Scaler(backend, scale_up_cooldown_seconds=0, scale_down_cooldown_seconds=0)
    policy = AutoscalerPolicy(
        workload=workload,
        namespace=namespace,
        target_queue_depth=target_queue_depth,
        scale_up_step=scale_up_step,
    )
    autoscaler = Autoscaler(collector, scaler, policy)

    base_time = datetime.now(timezone.utc)
    for i in range(ticks):
        # Advance simulated time by 5 minutes per tick.
        sim_now = base_time + timedelta(minutes=i * 5)
        decision = autoscaler.tick(now=sim_now)
        marker = {"up": "↑", "down": "↓", "hold": " "}[decision.direction.value]
        click.echo(
            f"t={i:02d}  {marker}  "
            f"replicas {decision.from_replicas:>2d}→{decision.to_replicas:<2d}  "
            f"queue={_synthetic_queue(i):>5.1f}  "
            f"reason={decision.reason}"
        )

    click.echo("\nSummary:")
    click.echo(f"  Scale-ups:   {sum(1 for d in autoscaler.decision_history if d.direction is ScaleDirection.UP)}")
    click.echo(f"  Scale-downs: {sum(1 for d in autoscaler.decision_history if d.direction is ScaleDirection.DOWN)}")
    click.echo(f"  Holds:       {sum(1 for d in autoscaler.decision_history if d.direction is ScaleDirection.HOLD)}")


@cli.command()
@click.option("--workload", default="ml-api")
@click.option("--namespace", default="ml")
@click.option("--replicas", default=3, type=int)
@click.option("--cpu", default=0.6, type=float)
@click.option("--memory", default=0.5, type=float)
@click.option("--gpu", default=0.0, type=float)
@click.option("--queue", default=5.0, type=float)
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "json"]))
def decide(
    workload: str,
    namespace: str,
    replicas: int,
    cpu: float,
    memory: float,
    gpu: float,
    queue: float,
    fmt: str,
) -> None:
    """Compute and print a single scaling decision."""
    metric = WorkloadMetric(
        workload=workload,
        namespace=namespace,
        replica_count=replicas,
        pod_metrics=[
            PodMetric(
                pod=f"{workload}-{i}",
                namespace=namespace,
                cpu_utilization=cpu,
                memory_utilization=memory,
                gpu_utilization=gpu,
            )
            for i in range(replicas)
        ],
        queue_depth=queue,
    )
    policy = AutoscalerPolicy(workload=workload, namespace=namespace)
    backend = InMemoryScalerBackend()
    backend.set_replicas(namespace, workload, replicas)
    autoscaler = Autoscaler(
        collector=MetricsCollector(prometheus_query=lambda q: []),
        scaler=Scaler(backend, scale_up_cooldown_seconds=0, scale_down_cooldown_seconds=0),
        policy=policy,
    )
    decision = autoscaler.decide(metric)
    if fmt == "json":
        click.echo(json.dumps({
            **{k: v for k, v in asdict(decision).items() if k != "timestamp"},
            "direction": decision.direction.value,
            "timestamp": decision.timestamp.isoformat(),
        }, indent=2))
    else:
        click.echo(
            f"{decision.direction.value:<5s} replicas {decision.from_replicas} → {decision.to_replicas}"
        )
        click.echo(f"  triggers: {decision.triggers or ['<none>']}")
        click.echo(f"  cost delta: ${decision.cost_delta_per_hour:+.4f}/hour")
        click.echo(f"  reason: {decision.reason}")


def _synthetic_queue(minute: int) -> float:
    phase = math.sin(minute / 30.0 * 2.0 * math.pi) * 0.5 + 0.5
    return max(0.0, (phase - 0.6) * 60)


if __name__ == "__main__":
    cli()
