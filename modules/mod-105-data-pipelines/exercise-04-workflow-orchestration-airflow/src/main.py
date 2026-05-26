"""
Workflow Orchestration — CLI

Subcommands:
    run         Execute the ML training DAG end-to-end and report the
                outcome of each task.
    plan        Print the topological execution order.
    inject-failure  Run the DAG with a forced failure to demonstrate
                the alert + skip flow.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict, List

import click

from .dags.ml_training_dag import (
    DAG,
    build_ml_training_dag,
    sample_dataset_loader,
    sample_feature_fn,
    sample_training_fn,
)
from .operators.custom_operators import TaskInstance


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """ML workflow orchestrator."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
def plan() -> None:
    """Print the topological execution order of the ML training DAG."""
    dag = build_ml_training_dag()
    for i, operator in enumerate(dag.topological_order(), start=1):
        deps = f" depends_on={operator.depends_on}" if operator.depends_on else ""
        click.echo(f"  {i}. {operator.task_id}{deps}")


@cli.command()
@click.option("--rows", default=500, type=int)
@click.option("--seed", default=42, type=int)
def run(rows: int, seed: int) -> None:
    """Execute the DAG end-to-end."""
    def _loader(ti: TaskInstance) -> List[Dict[str, Any]]:
        return sample_dataset_loader(ti, seed=seed, row_count=rows)

    dag = build_ml_training_dag(dataset_loader=_loader)
    report = dag.run()
    click.echo(f"DAG: {report.dag_id}")
    click.echo(f"Duration: {report.duration_seconds:.3f}s")
    click.echo(f"Successful: {report.successful_tasks}")
    click.echo(f"Skipped:    {report.skipped_tasks}")
    click.echo(f"Failed:     {report.failed_tasks}")
    click.echo()
    for task_id, result in report.results.items():
        marker = {
            "success": "✓", "retried": "✓", "failed": "✗",
            "skipped": "○",
        }.get(result.state.value, "?")
        click.echo(
            f"  {marker} {task_id:<25s} state={result.state.value:<10s} "
            f"attempts={result.attempts} duration={result.duration_seconds:.3f}s"
        )
    if not report.passed:
        sys.exit(2)


@cli.command()
@click.option("--rows", default=50, type=int,
              help="Below the min_rows threshold to trip validation")
def inject_failure(rows: int) -> None:
    """Force validation failure to exercise the alert + skip flow."""
    def _loader(ti: TaskInstance) -> List[Dict[str, Any]]:
        return sample_dataset_loader(ti, row_count=rows)
    dag = build_ml_training_dag(dataset_loader=_loader)
    report = dag.run()
    click.echo(f"DAG: {report.dag_id}")
    click.echo(f"Failed: {report.failed_tasks}")
    click.echo(f"Skipped: {report.skipped_tasks}")
    click.echo(f"Successful: {report.successful_tasks}")


if __name__ == "__main__":
    cli()
