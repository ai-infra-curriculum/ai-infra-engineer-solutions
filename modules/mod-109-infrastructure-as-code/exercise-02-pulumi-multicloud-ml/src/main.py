"""
Multi-Cloud ML Infrastructure (Pulumi-style) — CLI

Subcommands:
    build       Build a stack and print the resource graph.
    diff        Diff two stack variants (e.g., with vs without TPU).
    cost        Estimate monthly cost.
    json        Emit the full stack as Pulumi-shaped JSON.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Optional

import click

from .infrastructure import (
    MultiCloudMLPlatform,
    diff_stacks,
    estimate_cost,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _project_options(f):
    f = click.option("--stack", default="dev")(f)
    f = click.option("--project", default="ml-platform")(f)
    return f


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Multi-cloud ML infrastructure (Pulumi-style)."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@_project_options
@click.option("--include-tpu/--no-tpu", default=True)
def build(project: str, stack: str, include_tpu: bool) -> None:
    """Build a stack and summarize the resource graph."""
    platform = MultiCloudMLPlatform(project_name=project, stack_name=stack)
    s = platform.build(include_tpu=include_tpu)
    click.echo(f"Stack: {s.name}  resources={len(s.resources)}  outputs={len(s.outputs)}")
    by_provider = {}
    for r in s.resources:
        by_provider.setdefault(r.id.provider.value, []).append(r)
    for provider, resources in sorted(by_provider.items()):
        click.echo(f"\n  {provider.upper()}:")
        for r in resources:
            click.echo(f"    {r.id.resource_type:<40s} {r.id.logical_name}")


@cli.command()
@_project_options
def diff(project: str, stack: str) -> None:
    """Diff stack with TPU vs without TPU to demonstrate change detection."""
    platform = MultiCloudMLPlatform(project_name=project, stack_name=stack)
    previous = platform.build(include_tpu=True)
    current = platform.build(include_tpu=False)
    delta = diff_stacks(previous, current)
    click.echo(f"Changes between TPU-enabled and TPU-disabled:")
    click.echo(f"  to create:  {len(delta.to_create)}")
    click.echo(f"  to update:  {len(delta.to_update)}")
    click.echo(f"  to delete:  {len(delta.to_delete)}")
    for d in delta.diffs:
        click.echo(f"  {d.operation:<7s} {d.urn}")


@cli.command()
@_project_options
def cost(project: str, stack: str) -> None:
    """Estimate monthly cost for the stack."""
    platform = MultiCloudMLPlatform(project_name=project, stack_name=stack)
    s = platform.build()
    breakdown = estimate_cost(s)
    click.echo(f"Monthly cost for {project} ({stack}):")
    click.echo(f"  AWS compute (EKS): ${breakdown.aws_compute_usd:>9,.2f}")
    click.echo(f"  AWS storage (S3):  ${breakdown.aws_storage_usd:>9,.2f}")
    click.echo(f"  GCP TPU:           ${breakdown.gcp_tpu_usd:>9,.2f}")
    click.echo(f"  Azure Monitor:     ${breakdown.azure_monitor_usd:>9,.2f}")
    click.echo(f"  ---------------------------")
    click.echo(f"  Total:             ${breakdown.total_usd:>9,.2f}")


@cli.command(name="json")
@_project_options
def emit_json(project: str, stack: str) -> None:
    """Emit the stack as Pulumi-shaped JSON."""
    platform = MultiCloudMLPlatform(project_name=project, stack_name=stack)
    s = platform.build()
    click.echo(json.dumps(s.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    cli()
