"""
ModelDeployment Operator — CLI Entry Point

Subcommands:
    reconcile   Apply a ModelDeployment CR YAML and print the resulting
                derived-resource set + status.
    crd         Emit the CRD OpenAPIv3 schema fragment.
    rollback    Force a rollback drill by injecting failure_count.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

import click
import yaml

from .crd import (
    ModelDeploymentStatus,
    to_openapi_v3,
)
from .operator import (
    InMemoryK8sClient,
    K8sResource,
    ModelDeploymentOperator,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _load_cr(path: Path) -> Dict[str, Any]:
    """Load a ModelDeployment CR YAML body."""
    document = yaml.safe_load(path.read_text())
    if document.get("kind") != "ModelDeployment":
        raise click.UsageError(
            f"Expected kind: ModelDeployment, got {document.get('kind')!r}"
        )
    return document


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def cli(verbose: bool) -> None:
    """ModelDeployment operator."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.argument("cr_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--namespace", default="default")
@click.option("--simulate-not-ready", default=0, type=int,
              help="Force pre-set ready replicas (for testing degraded paths)")
def reconcile(cr_path: str, namespace: str, simulate_not_ready: int) -> None:
    """Reconcile a ModelDeployment CR."""
    cr = _load_cr(Path(cr_path))
    name = cr["metadata"]["name"]
    client = InMemoryK8sClient()
    operator = ModelDeploymentOperator(client)
    if simulate_not_ready > 0:
        # Pre-create the Deployment so deployment_status reads from it.
        # Then override the status to simulate partial readiness.
        client.set_deployment_status(
            namespace, name,
            desired=cr["spec"].get("replicas", 2),
            ready=simulate_not_ready,
        )
    result = operator.reconcile(
        namespace=namespace,
        name=name,
        spec_body=cr["spec"],
    )
    click.echo("Reconciliation actions:")
    for action in result.actions:
        click.echo(f"  - {action}")
    click.echo("\nDerived resources:")
    for kind in ("Deployment", "Service", "HorizontalPodAutoscaler"):
        resource = client.get(kind, namespace, name)
        if resource is None:
            click.echo(f"  {kind}: <not created>")
            continue
        click.echo(f"  {kind}: {resource.namespace}/{resource.name}")
    click.echo("\nStatus:")
    click.echo(json.dumps(result.status.to_dict(), indent=2))


@cli.command()
def crd() -> None:
    """Emit the OpenAPIv3Schema fragment for the CRD."""
    click.echo(json.dumps(to_openapi_v3(), indent=2))


@cli.command()
@click.argument("cr_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--namespace", default="default")
def rollback(cr_path: str, namespace: str) -> None:
    """Force a rollback drill: inject failure_count and reconcile."""
    cr = _load_cr(Path(cr_path))
    if not cr["spec"].get("previousVersion"):
        raise click.UsageError(
            "spec.previousVersion must be set on the CR for rollback drill."
        )
    name = cr["metadata"]["name"]
    client = InMemoryK8sClient()
    # 0 ready replicas, threshold-many failures already recorded.
    client.set_deployment_status(namespace, name, desired=cr["spec"].get("replicas", 2), ready=0)
    pre_status = ModelDeploymentStatus(failure_count=3)
    operator = ModelDeploymentOperator(client)
    result = operator.reconcile(
        namespace=namespace, name=name,
        spec_body=cr["spec"], status=pre_status,
    )
    click.echo(f"Rollback triggered: {result.triggered_rollback}")
    click.echo("Actions:")
    for action in result.actions:
        click.echo(f"  - {action}")
    click.echo(f"\nDeployed version after rollback: {result.status.deployed_version}")


if __name__ == "__main__":
    cli()
