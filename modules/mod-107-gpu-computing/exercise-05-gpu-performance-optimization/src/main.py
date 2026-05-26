"""
GPU Performance Optimization — CLI

Subcommands:
    profile     Collect a synthetic profile run and print the
                bottleneck report.
    optimize    Print ranked optimization recommendations + expected
                aggregate speedup for a given scenario.
    regression  Compare two scenarios (baseline vs candidate) and
                report whether the candidate is regressing.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Dict, Optional

import click

from .optimizer import (
    PerformanceOptimizer,
    detect_regression,
)
from .profiler import (
    BottleneckAnalyzer,
    SyntheticTraceProfile,
    SyntheticTraceSource,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


_SCENARIOS = {
    "data_loader_bound": SyntheticTraceProfile(
        data_loading_ms=140.0, h2d_copy_ms=10.0, forward_ms=60.0,
        backward_ms=70.0, optimizer_ms=10.0, idle_ms=5.0,
        allocated_gb=8.0, peak_gb=10.0, capacity_gb=40.0,
    ),
    "compute_bound": SyntheticTraceProfile(
        data_loading_ms=20.0, h2d_copy_ms=5.0, forward_ms=200.0,
        backward_ms=320.0, optimizer_ms=30.0, idle_ms=3.0,
        allocated_gb=32.0, peak_gb=38.0, capacity_gb=40.0,
    ),
    "memory_bound": SyntheticTraceProfile(
        data_loading_ms=20.0, h2d_copy_ms=40.0, forward_ms=60.0,
        backward_ms=80.0, optimizer_ms=10.0, idle_ms=5.0,
        allocated_gb=37.0, peak_gb=39.0, capacity_gb=40.0,
    ),
    "multi_gpu_unbalanced": SyntheticTraceProfile(
        data_loading_ms=30.0, h2d_copy_ms=8.0, forward_ms=90.0,
        backward_ms=120.0, optimizer_ms=12.0, collective_ms=80.0,
        idle_ms=10.0, device_count=4,
        allocated_gb=20.0, peak_gb=24.0, capacity_gb=40.0,
    ),
    "balanced": SyntheticTraceProfile(),
}


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """GPU performance optimizer."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--scenario", default="balanced",
              type=click.Choice(list(_SCENARIOS.keys())))
@click.option("--steps", default=50, type=int)
@click.option("--batch-size", default=32, type=int)
def profile(scenario: str, steps: int, batch_size: int) -> None:
    """Run a synthetic profile and print the bottleneck report."""
    source = SyntheticTraceSource(_SCENARIOS[scenario])
    run = source.collect(steps=steps, batch_size=batch_size)
    single_device_tp = None
    if scenario == "multi_gpu_unbalanced":
        single_device_tp = 280.0
    report = BottleneckAnalyzer().analyze(run, single_device_throughput=single_device_tp)
    click.echo(f"Scenario: {scenario}")
    click.echo(f"Steps: {len(run.steps)} batch_size={batch_size} devices={run.device_count}")
    click.echo(f"Primary bottleneck: {report.primary_bottleneck.value}")
    click.echo(f"Avg throughput: {report.avg_throughput_samples_per_sec:.1f} samples/sec")
    click.echo(f"GPU compute: {report.gpu_compute_percent:.1f}%   "
               f"Data loading: {report.data_loading_percent:.1f}%   "
               f"Mem move: {report.memory_movement_percent:.1f}%   "
               f"Collectives: {report.collective_percent:.1f}%   "
               f"Idle: {report.idle_percent:.1f}%")
    click.echo(f"Memory utilization: {report.avg_gpu_memory_utilization_percent:.1f}%")
    if report.multi_gpu_scaling_efficiency_percent is not None:
        click.echo(f"Scaling efficiency: {report.multi_gpu_scaling_efficiency_percent:.1f}%")
    click.echo("\nBreakdown:")
    for b in report.breakdown:
        click.echo(f"  {b.category.value:<14s} "
                   f"{b.total_ms:>10.1f} ms  {b.percent:>5.1f}%  "
                   f"({b.count} events)")


@cli.command()
@click.option("--scenario", default="balanced",
              type=click.Choice(list(_SCENARIOS.keys())))
def optimize(scenario: str) -> None:
    """Print recommendations + aggregate speedup."""
    source = SyntheticTraceSource(_SCENARIOS[scenario])
    run = source.collect(steps=50, batch_size=32)
    single_device_tp = 280.0 if scenario == "multi_gpu_unbalanced" else None
    report = BottleneckAnalyzer().analyze(run, single_device_throughput=single_device_tp)
    plan = PerformanceOptimizer().recommend(report)
    click.echo(f"Scenario: {scenario}")
    click.echo(f"Expected aggregate speedup: {plan.expected_aggregate_speedup}x")
    for rec in plan.recommendations:
        click.echo(
            f"\n  [{rec.confidence.value:<6s}] {rec.title}  "
            f"(~{rec.estimated_throughput_increase_percent:.0f}% throughput gain)"
        )
        click.echo(f"    {rec.description}")
        click.echo(f"    action: {rec.action}")


@cli.command()
@click.option("--baseline", default="balanced",
              type=click.Choice(list(_SCENARIOS.keys())))
@click.option("--candidate", default="data_loader_bound",
              type=click.Choice(list(_SCENARIOS.keys())))
@click.option("--threshold-percent", default=5.0, type=float)
def regression(baseline: str, candidate: str, threshold_percent: float) -> None:
    """Compare two scenarios and report regression."""
    analyzer = BottleneckAnalyzer()
    base_run = SyntheticTraceSource(_SCENARIOS[baseline]).collect(steps=50, batch_size=32)
    cand_run = SyntheticTraceSource(_SCENARIOS[candidate]).collect(steps=50, batch_size=32)
    base_report = analyzer.analyze(base_run)
    cand_report = analyzer.analyze(cand_run)
    result = detect_regression(base_report, cand_report, threshold_percent=threshold_percent)
    click.echo(f"Baseline throughput:  {result.baseline_throughput:.1f} samples/sec")
    click.echo(f"Candidate throughput: {result.candidate_threshold_throughput:.1f} samples/sec")
    click.echo(f"Delta: {result.delta_percent:+.2f}%   threshold: ±{result.threshold_percent}%")
    click.echo(f"Regressed: {'YES' if result.regressed else 'NO'}")
    if result.regressed:
        sys.exit(2)


if __name__ == "__main__":
    cli()
