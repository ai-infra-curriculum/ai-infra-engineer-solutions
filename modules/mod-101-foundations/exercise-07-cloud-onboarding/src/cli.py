"""cloud-onboard CLI."""
from __future__ import annotations

import json
import logging

import click

from . import state
from .providers.aws import AWSProvider


logging.basicConfig(level=logging.INFO, format="%(message)s")


@click.group()
def cli() -> None:
    """Bootstrap a per-user cloud sandbox."""


@cli.command()
@click.option("--user", required=True)
@click.option("--provider", default="aws", type=click.Choice(["aws"]))
@click.option("--region", default="us-west-2")
@click.option("--dry-run", is_flag=True)
def init(user: str, provider: str, region: str, dry_run: bool) -> None:
    if dry_run:
        click.echo(f"DRY-RUN: would provision {user}@{provider}:{region}")
        return
    p = AWSProvider(region=region)
    out = p.init(user, region)
    state.save(user, {
        "provider": provider, "region": region,
        "iam_principal": out.iam_principal, "bucket": out.bucket,
    })
    env_path = state.write_env(user, out.creds)
    click.echo(f"provisioned. creds written to {env_path}")
    click.echo(f"  source: {env_path}")


@cli.command()
@click.option("--user", required=True)
def status(user: str) -> None:
    p = AWSProvider()
    click.echo(json.dumps(list(p.status(user).items()), default=str, indent=2))


@cli.command()
@click.option("--user", required=True)
def rotate_key(user: str) -> None:
    p = AWSProvider()
    new = p.rotate_key(user)
    state.write_env(user, new)
    click.echo(f"rotated; new key id: {new['AWS_ACCESS_KEY_ID']}")


@cli.command()
@click.option("--user", required=True)
def destroy(user: str) -> None:
    p = AWSProvider()
    p.destroy(user)
    state.save(user, {})
    click.echo(f"destroyed sandbox for {user}")


if __name__ == "__main__":
    cli()
