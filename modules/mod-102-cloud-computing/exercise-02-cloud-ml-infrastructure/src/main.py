"""
Cloud ML Infrastructure Provisioner - CLI Entry Point

Generate per-cloud deployment plans for a portable ML infrastructure
stack (Kubernetes + object storage + managed Postgres + managed Redis +
load balancer + networking + monitoring). The CLI emits JSON plans the
caller hands to Terraform or a console.

Subcommands:
    plan    Render a plan for one cloud (--provider).
    diff    Render plans for all three clouds and summarize differences.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .provisioner import (
    CloudProvider,
    ClusterSize,
    InfrastructureRequest,
    get_provisioner,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """Cloud ML Infrastructure Provisioner."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def _build_request(
    project: str,
    environment: str,
    region: str,
    cluster_size: str,
    enable_gpu: bool,
    gpu_count: int,
    database_storage_gb: int,
    cache_memory_gb: int,
    ha_database: bool,
    tags: tuple[str, ...],
) -> InfrastructureRequest:
    tag_dict = {}
    for entry in tags:
        if "=" not in entry:
            raise click.UsageError(f"Tag entries must be key=value, got {entry!r}")
        k, v = entry.split("=", 1)
        tag_dict[k] = v
    return InfrastructureRequest(
        project_name=project,
        environment=environment,
        region=region,
        cluster_size=ClusterSize(cluster_size),
        enable_gpu=enable_gpu,
        gpu_count_per_node=gpu_count,
        database_storage_gb=database_storage_gb,
        cache_memory_gb=cache_memory_gb,
        enable_ha_database=ha_database,
        tags=tag_dict,
    )


_REQUEST_OPTIONS = [
    click.option("--project", default="ml-infra"),
    click.option("--environment", default="dev", type=click.Choice(["dev", "staging", "prod"])),
    click.option("--region", default="us-east-1"),
    click.option(
        "--cluster-size",
        default=ClusterSize.SMALL.value,
        type=click.Choice([s.value for s in ClusterSize]),
    ),
    click.option("--enable-gpu/--no-gpu", default=False),
    click.option("--gpu-count", default=0, type=int),
    click.option("--database-storage-gb", default=100, type=int),
    click.option("--cache-memory-gb", default=2, type=int),
    click.option("--ha-database/--no-ha-database", default=True),
    click.option("--tag", "tags", multiple=True, help="key=value (repeatable)"),
]


def _add_request_options(f):
    for opt in reversed(_REQUEST_OPTIONS):
        f = opt(f)
    return f


@cli.command()
@click.option("--provider", required=True, type=click.Choice([p.value for p in CloudProvider]))
@click.option("--output", type=click.Path(dir_okay=False), help="Write plan JSON to file")
@_add_request_options
def plan(provider: str, output: Optional[str], **kwargs) -> None:
    """Render a deployment plan for one cloud."""
    request = _build_request(**kwargs)
    provisioner_cls = get_provisioner(CloudProvider(provider))
    deployment_plan = provisioner_cls().plan(request)
    body = json.dumps(deployment_plan.to_dict(), indent=2)
    if output:
        Path(output).write_text(body)
        click.echo(f"Plan written to {output}")
    else:
        click.echo(body)


@cli.command()
@_add_request_options
def diff(**kwargs) -> None:
    """Render plans for all clouds and summarize the resource shape."""
    request = _build_request(**kwargs)
    rows = []
    for provider in CloudProvider:
        provisioner_cls = get_provisioner(provider)
        result = provisioner_cls().plan(request)
        rows.append((provider.value, result))

    click.echo(f"Cluster size: {request.cluster_size.value}, GPU: {request.enable_gpu}")
    click.echo("=" * 70)
    click.echo(f"{'Resource':<22} {'AWS':<18} {'GCP':<18} {'Azure':<18}")
    click.echo("-" * 70)
    resource_types = [
        "kubernetes_cluster",
        "object_storage",
        "managed_database",
        "managed_cache",
        "load_balancer",
        "vpc",
        "monitoring",
    ]
    plans_by_provider = {name: plan for name, plan in rows}
    for rt in resource_types:
        cells = []
        for provider in CloudProvider:
            res = plans_by_provider[provider.value].find_resource(rt)
            if res is None:
                cells.append("-")
            else:
                service = str(res.settings.get("service") or res.settings.get("engine") or rt)
                cells.append(service[:18])
        click.echo(f"{rt:<22} {cells[0]:<18} {cells[1]:<18} {cells[2]:<18}")

    click.echo()
    for name, plan in rows:
        if plan.warnings:
            click.echo(f"[{name}] warnings:")
            for w in plan.warnings:
                click.echo(f"  - {w}")


@cli.command()
def validate() -> None:
    """Smoke test: render plans for all 3 clouds with default parameters."""
    request = InfrastructureRequest(
        project_name="smoke",
        environment="dev",
        region="us-east-1",
        cluster_size=ClusterSize.SMALL,
    )
    for provider in CloudProvider:
        provisioner_cls = get_provisioner(provider)
        plan = provisioner_cls().plan(request)
        assert len(plan.resources) >= 6, f"{provider.value}: expected >=6 resources"
        click.echo(f"OK   {provider.value}: {len(plan.resources)} resources")


if __name__ == "__main__":
    cli()
