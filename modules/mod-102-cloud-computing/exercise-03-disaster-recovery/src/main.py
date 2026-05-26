"""
Disaster Recovery System - CLI Entry Point

Manages backups, replication, restores, and DR drills for ML
infrastructure. The CLI uses a local filesystem store by default so
the system can be exercised end-to-end without cloud credentials.

Subcommands:
    backup      Create a backup of a source.
    restore     Restore the latest backup for a source.
    list        Show backup inventory.
    drill       Run a DR drill and report achieved RTO/RPO.
    prune       Delete expired backups.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import click

from .backup_manager import (
    BackupManager,
    BackupSource,
    BackupType,
    LocalStorageBackend,
    RetentionTier,
)
from .recovery_manager import HealthCheckResult, RecoveryManager, ServiceTier


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class _AlwaysHealthy:
    """Default HealthCheck used by the CLI demo paths."""

    def check(self, service: str) -> HealthCheckResult:
        return HealthCheckResult(service=service, healthy=True, response_time_ms=12.0)


def _make_manager(base: Path, replica_region: str = "us-west-2") -> BackupManager:
    primary = LocalStorageBackend(root=base / "primary", region="us-east-1")
    replica = LocalStorageBackend(root=base / "replica", region=replica_region)
    manifest = base / "manifest.json"
    return BackupManager(primary, replica_storage=replica, manifest_path=manifest)


@click.group()
@click.option("--store", "store", default=".dr-store", type=click.Path(file_okay=False))
@click.pass_context
def cli(ctx: click.Context, store: str) -> None:
    """Disaster Recovery System CLI."""
    ctx.ensure_object(dict)
    ctx.obj["store_path"] = Path(store)
    ctx.obj["manager"] = _make_manager(Path(store))


@cli.command()
@click.option("--source", required=True, type=click.Choice([s.value for s in BackupSource]))
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--retention", default="daily", type=click.Choice([t.value for t in RetentionTier]))
@click.option("--replicate/--no-replicate", default=True)
@click.option("--tag", "tags", multiple=True)
@click.pass_context
def backup(
    ctx: click.Context,
    source: str,
    input_path: str,
    retention: str,
    replicate: bool,
    tags: tuple[str, ...],
) -> None:
    """Back up a file as the given source type."""
    manager: BackupManager = ctx.obj["manager"]
    payload = Path(input_path).read_bytes()
    tag_dict: Dict[str, str] = {}
    for entry in tags:
        if "=" not in entry:
            raise click.UsageError(f"Tag entries must be key=value, got {entry!r}")
        k, v = entry.split("=", 1)
        tag_dict[k] = v
    metadata = manager.backup(
        BackupSource(source),
        payload,
        retention_tier=RetentionTier(retention),
        tags=tag_dict,
    )
    if replicate:
        manager.replicate(metadata.backup_id)
    click.echo(f"Backup {metadata.backup_id} created ({metadata.size_bytes} bytes)")
    click.echo(f"Checksum: {metadata.checksum_sha256[:16]}...")
    click.echo(f"Replicated regions: {metadata.replicated_regions or '[]'}")


@cli.command()
@click.option("--source", required=True, type=click.Choice([s.value for s in BackupSource]))
@click.option("--output", required=True, type=click.Path(dir_okay=False))
@click.option("--at", "target_time", default=None, help="ISO timestamp for point-in-time recovery")
@click.pass_context
def restore(ctx: click.Context, source: str, output: str, target_time: str | None) -> None:
    """Restore the latest backup for a source (or the latest at-or-before --at)."""
    manager: BackupManager = ctx.obj["manager"]
    recovery = RecoveryManager(manager, _AlwaysHealthy())
    when = datetime.fromisoformat(target_time) if target_time else None
    payload = recovery.restore(BackupSource(source), target_time=when)
    Path(output).write_bytes(payload)
    click.echo(f"Restored {len(payload)} bytes to {output}")


@cli.command()
@click.pass_context
def list_(ctx: click.Context) -> None:
    """Show backup inventory."""
    manager: BackupManager = ctx.obj["manager"]
    items = sorted(manager.list_backups(), key=lambda m: m.created_at, reverse=True)
    if not items:
        click.echo("(no backups)")
        return
    for m in items:
        click.echo(
            f"{m.backup_id:48s} {m.source.value:18s} "
            f"{m.retention_tier.value:8s} {m.size_bytes:>10d} bytes "
            f"created={m.created_at.isoformat(timespec='seconds')}"
        )


cli.add_command(list_, name="list")


@cli.command()
@click.option("--service", required=True)
@click.option("--tier", default="critical", type=click.Choice([t.value for t in ServiceTier]))
@click.option("--source", required=True, type=click.Choice([s.value for s in BackupSource]))
@click.pass_context
def drill(ctx: click.Context, service: str, tier: str, source: str) -> None:
    """Run a DR drill and report achieved RTO/RPO vs targets."""
    manager: BackupManager = ctx.obj["manager"]
    recovery = RecoveryManager(manager, _AlwaysHealthy())
    recovery.register_service(
        service=service,
        tier=ServiceTier(tier),
        region_primary="us-east-1",
        region_secondary="us-west-2",
    )
    result = recovery.run_drill(service=service, source=BackupSource(source))
    rto_status = "PASS" if result.rto_met else "FAIL"
    rpo_status = "PASS" if result.rpo_met else "FAIL"
    click.echo(f"Service:      {service} (tier={tier})")
    click.echo(f"Backup used:  {result.backup_used.backup_id}")
    click.echo(f"Achieved RTO: {result.achieved_rto.total_seconds():.3f}s  [{rto_status}]")
    click.echo(f"Achieved RPO: {result.achieved_rpo.total_seconds():.0f}s  [{rpo_status}]")
    sys.exit(0 if result.passed else 1)


@cli.command()
@click.pass_context
def prune(ctx: click.Context) -> None:
    """Delete backups past their retention horizon."""
    manager: BackupManager = ctx.obj["manager"]
    removed = manager.prune_expired(now=datetime.now(timezone.utc))
    click.echo(f"Pruned {len(removed)} expired backups")
    for backup_id in removed:
        click.echo(f"  - {backup_id}")


if __name__ == "__main__":
    cli()
