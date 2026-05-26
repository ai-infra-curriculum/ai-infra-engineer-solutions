"""
Terraform ML Infrastructure — CLI

Subcommands:
    generate    Emit HCL for one environment.
    validate    Validate a generated module against policy rules.
    cost        Estimate monthly cost for one environment.
    compare     Print a per-environment cost + sizing summary.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .terraform_builder import (
    CostEstimate,
    Environment,
    EnvironmentSpec,
    MLInfrastructureBuilder,
    PlatformConfig,
    estimate_monthly_cost,
    validate_module,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _project_options(f):
    f = click.option("--owner", default="ml-platform")(f)
    f = click.option("--region", default="us-east-1")(f)
    f = click.option("--project", default="ml-platform")(f)
    return f


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """Terraform ML infrastructure tooling."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@_project_options
@click.option("--env", "environment", default="dev",
              type=click.Choice([e.value for e in Environment]))
@click.option("--output", "-o", type=click.Path(dir_okay=False))
def generate(
    project: str, region: str, owner: str,
    environment: str, output: Optional[str],
) -> None:
    """Emit HCL for one environment."""
    platform = PlatformConfig(project_name=project, region=region, owner=owner)
    env_spec = EnvironmentSpec.for_environment(Environment(environment))
    module = MLInfrastructureBuilder(platform, env_spec).build()
    hcl = module.to_hcl()
    if output:
        Path(output).write_text(hcl)
        click.echo(f"Wrote {output} ({len(hcl)} bytes)")
    else:
        click.echo(hcl)


@cli.command()
@_project_options
@click.option("--env", "environment", default="dev",
              type=click.Choice([e.value for e in Environment]))
def validate(
    project: str, region: str, owner: str, environment: str,
) -> None:
    """Validate the generated module."""
    platform = PlatformConfig(project_name=project, region=region, owner=owner)
    env_spec = EnvironmentSpec.for_environment(Environment(environment))
    module = MLInfrastructureBuilder(platform, env_spec).build()
    report = validate_module(module, platform=platform, env=env_spec)
    click.echo(f"Validation: {'PASS' if report.passed else 'FAIL'}")
    click.echo(f"  resources: {len(module.resources)}")
    click.echo(f"  outputs:   {len(module.outputs)}")
    click.echo(f"  findings:  {len(report.issues)}")
    for issue in report.issues:
        click.echo(f"    [{issue.severity:<7s}] {issue.rule_id}: {issue.message}")
    sys.exit(0 if report.passed else 2)


@cli.command()
@_project_options
@click.option("--env", "environment", default="dev",
              type=click.Choice([e.value for e in Environment]))
def cost(project: str, region: str, owner: str, environment: str) -> None:
    """Estimate monthly cost for one environment."""
    env_spec = EnvironmentSpec.for_environment(Environment(environment))
    estimate = estimate_monthly_cost(env_spec)
    click.echo(f"Monthly cost estimate for {environment}:")
    click.echo(f"  EKS compute:    ${estimate.eks_compute_usd:>9,.2f}")
    click.echo(f"  GPU compute:    ${estimate.gpu_compute_usd:>9,.2f}")
    click.echo(f"  RDS:            ${estimate.rds_usd:>9,.2f}")
    click.echo(f"  Redis:          ${estimate.redis_usd:>9,.2f}")
    click.echo(f"  S3 (~200GB):    ${estimate.s3_usd:>9,.2f}")
    click.echo(f"  NAT Gateway:    ${estimate.nat_gateway_usd:>9,.2f}")
    click.echo(f"  ---------------------------")
    click.echo(f"  Total:          ${estimate.total_usd:>9,.2f}")
    click.echo(
        f"  Cost alarm at:  ${env_spec.cost_alarm_monthly_usd:>9,.2f}/month"
    )


@cli.command()
def compare() -> None:
    """Compare dev / staging / prod side by side."""
    click.echo(
        f"{'Env':<10s} {'EKS nodes':<10s} {'GPU nodes':<10s} "
        f"{'RDS':<16s} {'Multi-AZ':<9s} {'Monthly $':>10s}"
    )
    click.echo("-" * 75)
    for env in Environment:
        spec = EnvironmentSpec.for_environment(env)
        estimate = estimate_monthly_cost(spec)
        click.echo(
            f"{env.value:<10s} "
            f"{spec.eks_node_count}-{spec.eks_node_max:<8} "
            f"{spec.gpu_node_count}-{spec.gpu_node_max:<8} "
            f"{spec.rds_instance_class:<16s} "
            f"{str(spec.rds_multi_az):<9s} "
            f"${estimate.total_usd:>9,.2f}"
        )


if __name__ == "__main__":
    cli()
