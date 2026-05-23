"""artifact-replicator CLI."""
from __future__ import annotations

import json
import logging
import time

import click

from .backends import S3Backend, parse_uri
from .manifest import Manifest
from .transfer import diff, replicate_many, verify_all


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _backend_from_uri(uri: str, endpoint_url: str | None) -> S3Backend:
    scheme, bucket, prefix = parse_uri(uri)
    if scheme != "s3":
        raise click.BadParameter(f"only s3:// URIs supported, got {scheme}://")
    return S3Backend(bucket=bucket, prefix=prefix, endpoint_url=endpoint_url)


@click.group()
def cli() -> None:
    """Cross-region artifact replicator."""


@cli.command()
@click.option("--src", required=True)
@click.option("--dst", required=True)
@click.option("--manifest-path", default="manifest.db")
@click.option("--aws-endpoint", default=None)
def status(src: str, dst: str, manifest_path: str, aws_endpoint: str | None) -> None:
    src_b = _backend_from_uri(src, aws_endpoint)
    dst_b = _backend_from_uri(dst, aws_endpoint)
    m = Manifest(manifest_path)
    report = diff(src_b, dst_b, m)
    click.echo(json.dumps({k: len(v) for k, v in report.items()}, indent=2))


@cli.command()
@click.option("--src", required=True)
@click.option("--dst", required=True)
@click.option("--manifest-path", default="manifest.db")
@click.option("--rate-mbps", default=None, type=float, help="bandwidth cap, megabits/sec")
@click.option("--concurrency", default=4)
@click.option("--aws-endpoint", default=None)
def sync(src: str, dst: str, manifest_path: str, rate_mbps: float | None,
          concurrency: int, aws_endpoint: str | None) -> None:
    src_b = _backend_from_uri(src, aws_endpoint)
    dst_b = _backend_from_uri(dst, aws_endpoint)
    m = Manifest(manifest_path)
    report = diff(src_b, dst_b, m)
    pending = report["new"] + report["updated"]
    click.echo(f"replicating {len(pending)} objects ({len(report['unchanged'])} unchanged)")
    if pending:
        result = replicate_many(src_b, dst_b, pending, m,
                                  concurrency=concurrency, rate_mbps=rate_mbps)
        click.echo(json.dumps(result, indent=2))


@cli.command()
@click.option("--src", required=True)
@click.option("--dst", required=True)
@click.option("--manifest-path", default="manifest.db")
@click.option("--poll-seconds", default=60)
@click.option("--rate-mbps", default=None, type=float)
@click.option("--concurrency", default=4)
@click.option("--aws-endpoint", default=None)
def watch(src: str, dst: str, manifest_path: str, poll_seconds: int,
           rate_mbps: float | None, concurrency: int, aws_endpoint: str | None) -> None:
    while True:
        ctx = click.get_current_context()
        ctx.invoke(sync, src=src, dst=dst, manifest_path=manifest_path,
                    rate_mbps=rate_mbps, concurrency=concurrency, aws_endpoint=aws_endpoint)
        time.sleep(poll_seconds)


@cli.command()
@click.option("--dst", required=True)
@click.option("--manifest-path", default="manifest.db")
@click.option("--aws-endpoint", default=None)
def verify(dst: str, manifest_path: str, aws_endpoint: str | None) -> None:
    dst_b = _backend_from_uri(dst, aws_endpoint)
    m = Manifest(manifest_path)
    bad = verify_all(dst_b, m)
    if bad:
        click.echo(f"FAIL: {len(bad)} mismatches: {bad[:10]}", err=True)
        raise SystemExit(1)
    click.echo("OK: all objects verified")


if __name__ == "__main__":
    cli()
