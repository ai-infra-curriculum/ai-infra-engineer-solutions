"""
GPU Cluster Management — CLI

Subcommands:
    demo        Build a synthetic 8-GPU cluster, submit a mix of jobs,
                schedule them with each strategy, and print the result.
    chargeback  Run a fixed scenario and print the team-cost report.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import timedelta
from typing import Dict, List

import click

from .cluster_manager import (
    ClusterManager,
    GpuDevice,
    GpuType,
    Node,
    Priority,
)
from .gpu_allocator import (
    BinPackingScheduler,
    FIFOScheduler,
    PriorityScheduler,
    schedule_and_apply,
)
from .monitoring import (
    CostAccountant,
    HealthMonitor,
    devices_by_type,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _build_cluster() -> ClusterManager:
    """4 nodes × 2 GPUs each, mix of T4/V100/A100."""
    manager = ClusterManager()
    layouts = [
        ("node-1", [GpuType.T4, GpuType.T4]),
        ("node-2", [GpuType.V100, GpuType.V100]),
        ("node-3", [GpuType.A100, GpuType.A100]),
        ("node-4", [GpuType.A100, GpuType.V100]),
    ]
    memory_by_type = {GpuType.T4: 16, GpuType.V100: 32, GpuType.A100: 80, GpuType.H100: 80}
    for node_id, gpu_types in layouts:
        devices = [
            GpuDevice(
                device_id=f"{node_id}-gpu-{i}",
                node_id=node_id,
                gpu_type=t,
                memory_gb=memory_by_type[t],
            )
            for i, t in enumerate(gpu_types)
        ]
        manager.register_node(Node(
            node_id=node_id, devices=devices, cpu_cores=64, memory_gb=256,
        ))
    manager.set_team_quota("alpha", max_gpu_fractions=4.0)
    manager.set_team_quota("beta", max_gpu_fractions=3.0)
    manager.set_team_quota("gamma", max_gpu_fractions=2.0)
    return manager


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """GPU cluster manager."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option(
    "--scheduler", "scheduler_name", default="priority",
    type=click.Choice(["fifo", "priority", "bin_packing"]),
)
def demo(scheduler_name: str) -> None:
    """Submit a mix of jobs and run one scheduling tick."""
    manager = _build_cluster()
    # Submit jobs that exceed the team quotas + capacity to surface
    # the scheduler's prioritization + preemption behavior.
    manager.submit_job(team="alpha", name="bert-train", requested_fraction=1.0,
                       requested_gpu_count=2, preferred_gpu_type=GpuType.A100,
                       priority=Priority.NORMAL)
    manager.submit_job(team="beta", name="resnet-train", requested_fraction=0.5,
                       requested_gpu_count=2, preferred_gpu_type=GpuType.V100,
                       priority=Priority.LOW)
    manager.submit_job(team="gamma", name="urgent-eval", requested_fraction=1.0,
                       requested_gpu_count=1, preferred_gpu_type=GpuType.A100,
                       priority=Priority.CRITICAL)
    manager.submit_job(team="alpha", name="t4-light", requested_fraction=0.25,
                       requested_gpu_count=2, preferred_gpu_type=GpuType.T4,
                       priority=Priority.NORMAL)
    manager.submit_job(team="beta", name="grid-search", requested_fraction=0.5,
                       requested_gpu_count=1, priority=Priority.LOW)

    scheduler = {
        "fifo": FIFOScheduler(),
        "priority": PriorityScheduler(),
        "bin_packing": BinPackingScheduler(),
    }[scheduler_name]
    plan = schedule_and_apply(manager, scheduler)
    click.echo(f"Scheduler: {scheduler.name}")
    click.echo(f"Assignments: {len(plan.assignments)}")
    for a in plan.assignments:
        click.echo(f"  {a.job_id} → {a.device_ids} ({a.reason})")
    if plan.preemptions:
        click.echo(f"Preemptions: {plan.preemptions}")
    if plan.rejections:
        click.echo(f"Rejected ({len(plan.rejections)}):")
        for r in plan.rejections:
            click.echo(f"  {r['job_id']}: {r['reason']}")
    click.echo(f"Cluster utilization: {manager.cluster_utilization():.0%}")


@cli.command()
def chargeback() -> None:
    """Run a deterministic scenario and print per-team chargeback."""
    manager = _build_cluster()
    accountant = CostAccountant()
    # Schedule + complete jobs of varying GPU types.
    a = manager.submit_job(team="alpha", name="train", requested_fraction=1.0,
                            preferred_gpu_type=GpuType.A100,
                            requested_gpu_count=1)
    b = manager.submit_job(team="beta", name="train", requested_fraction=1.0,
                            preferred_gpu_type=GpuType.V100,
                            requested_gpu_count=1)
    c = manager.submit_job(team="gamma", name="train", requested_fraction=0.5,
                            preferred_gpu_type=GpuType.T4,
                            requested_gpu_count=1)
    plan = schedule_and_apply(manager, PriorityScheduler())
    # Simulate runtime by mutating ended_at + completing.
    from datetime import datetime, timezone, timedelta
    for job in (a, b, c):
        if job.status.value == "running":
            assert job.started_at is not None
            # Bend the clock forward in the Job record directly.
            job.ended_at = job.started_at + timedelta(hours=2)
            counts = devices_by_type(manager, job.assigned_devices)
            accountant.record_completed(job, devices_by_type=counts)
            manager.complete_job(job.job_id)
    click.echo("Team chargeback (2-hour run):")
    for entry in accountant.report():
        gpu_breakdown = ", ".join(
            f"{t.value}={h:.2f}h" for t, h in entry.gpu_hours_by_type.items() if h > 0
        )
        click.echo(f"  {entry.team:<10s} ${entry.total_cost_usd:>8.2f}  [{gpu_breakdown}]")


if __name__ == "__main__":
    cli()
