"""
Container Registry Manager — CLI + orchestration layer

Exposes four operations across multiple registries:

- sync:       copy a tag (or all tags of a repository) from a source
              registry to one or more destinations, skipping tags whose
              digest already matches.
- promote:    move a tag through dev → staging → prod by retagging in
              the destination registry; promotions are gated by an
              approver hook so the caller can require sign-off.
- retention:  apply RetentionRules to a registry, deleting tags that
              are old, unused, and not protected.
- audit:      append-only audit log of every operation; emits JSON
              entries the caller persists to a sink of their choice.

The CLI uses an in-memory registry by default so the system is
end-to-end demonstrable without cloud credentials.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import click

from .registry.acr import ACRRegistry
from .registry.base import (
    ImageManifest,
    ImageTag,
    InMemoryRegistry,
    Registry,
    RegistryError,
    RetentionRule,
)
from .registry.ecr import ECRRegistry
from .registry.gcr import GCRRegistry


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# -- Audit ---------------------------------------------------------------


class AuditAction(str, Enum):
    SYNC = "sync"
    PROMOTE = "promote"
    DELETE = "delete"
    PUSH = "push"


@dataclass
class AuditEntry:
    action: AuditAction
    actor: str
    timestamp: datetime
    source: Optional[str]
    destination: Optional[str]
    repository: str
    tag: str
    digest: str
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "actor": self.actor,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "destination": self.destination,
            "repository": self.repository,
            "tag": self.tag,
            "digest": self.digest,
            "note": self.note,
        }


class AuditLog:
    """Append-only audit log written to a JSONL file (or in-memory)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path
        self.entries: List[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self.entries.append(entry)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

    def filter(
        self,
        *,
        action: Optional[AuditAction] = None,
        repository: Optional[str] = None,
    ) -> List[AuditEntry]:
        results = self.entries
        if action is not None:
            results = [e for e in results if e.action is action]
        if repository is not None:
            results = [e for e in results if e.repository == repository]
        return results


# -- Sync ----------------------------------------------------------------


@dataclass
class SyncReport:
    copied: List[str] = field(default_factory=list)
    skipped_same_digest: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)


def sync_tag(
    source: Registry,
    destination: Registry,
    repository: str,
    tag: str,
    audit: AuditLog,
    actor: str = "system",
) -> SyncReport:
    """Sync one tag; skip if destination already has the same digest."""
    report = SyncReport()
    src_tag = source.get_tag(repository, tag)
    try:
        dest_tag = destination.get_tag(repository, tag)
        if dest_tag.manifest.digest == src_tag.manifest.digest:
            report.skipped_same_digest.append(src_tag.reference)
            return report
    except RegistryError:
        pass  # destination doesn't have the tag yet — copy below

    destination.push(repository, tag, src_tag.manifest)
    report.copied.append(src_tag.reference)
    audit.append(AuditEntry(
        action=AuditAction.SYNC,
        actor=actor,
        timestamp=datetime.now(timezone.utc),
        source=source.name,
        destination=destination.name,
        repository=repository,
        tag=tag,
        digest=src_tag.manifest.digest,
    ))
    return report


def sync_repository(
    source: Registry,
    destinations: Iterable[Registry],
    repository: str,
    audit: AuditLog,
    actor: str = "system",
) -> Dict[str, SyncReport]:
    """Sync every tag in `repository` to each destination."""
    src_tags = source.list_tags(repository)
    reports: Dict[str, SyncReport] = {}
    for dest in destinations:
        report = SyncReport()
        for src_tag in src_tags:
            try:
                partial = sync_tag(source, dest, repository, src_tag.tag, audit, actor)
                report.copied.extend(partial.copied)
                report.skipped_same_digest.extend(partial.skipped_same_digest)
            except Exception as exc:  # pragma: no cover - safety net
                logger.warning("Sync of %s failed: %s", src_tag.reference, exc)
                report.failed.append(src_tag.reference)
        reports[dest.name] = report
    return reports


# -- Promotion -----------------------------------------------------------


class PromotionStage(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


# (current, next) graph for the standard pipeline.
_NEXT_STAGE = {
    PromotionStage.DEV: PromotionStage.STAGING,
    PromotionStage.STAGING: PromotionStage.PROD,
}


@dataclass
class PromotionResult:
    repository: str
    from_tag: str
    to_tag: str
    digest: str
    approved_by: str


def promote(
    registry: Registry,
    repository: str,
    source_tag: str,
    target_stage: PromotionStage,
    audit: AuditLog,
    *,
    approver: Callable[[str, str, str], bool] = lambda r, t, s: True,
    actor: str = "ci",
) -> PromotionResult:
    """
    Promote `repository:source_tag` to `repository:<target_stage>`.

    The approver callback receives (repository, source_tag, target_stage)
    and must return True for the promotion to proceed.
    """
    src = registry.get_tag(repository, source_tag)
    target_tag = target_stage.value
    if not approver(repository, source_tag, target_tag):
        raise PermissionError(
            f"Promotion of {repository}:{source_tag} to {target_tag} was denied by approver."
        )
    registry.push(repository, target_tag, src.manifest)
    audit.append(AuditEntry(
        action=AuditAction.PROMOTE,
        actor=actor,
        timestamp=datetime.now(timezone.utc),
        source=registry.name,
        destination=registry.name,
        repository=repository,
        tag=target_tag,
        digest=src.manifest.digest,
        note=f"promoted from {source_tag}",
    ))
    return PromotionResult(
        repository=repository,
        from_tag=source_tag,
        to_tag=target_tag,
        digest=src.manifest.digest,
        approved_by=actor,
    )


# -- Retention -----------------------------------------------------------


@dataclass
class RetentionReport:
    deleted: List[str] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)
    protected: List[str] = field(default_factory=list)


def apply_retention(
    registry: Registry,
    rules: List[RetentionRule],
    audit: AuditLog,
    actor: str = "retention-system",
    now: Optional[datetime] = None,
) -> RetentionReport:
    """Delete tags that exceed any matching retention rule."""
    now = now or datetime.now(timezone.utc)
    report = RetentionReport()
    for repository in registry.list_repositories():
        applicable = [r for r in rules if r.matches_repository(repository)]
        if not applicable:
            report.kept.extend(t.reference for t in registry.list_tags(repository))
            continue
        # Most-specific (non-"*") rule wins.
        rule = sorted(
            applicable,
            key=lambda r: r.repository_pattern == "*",
        )[0]
        tags = registry.list_tags(repository)
        # Always retain the most-recent N.
        keep_indices = set(range(min(rule.keep_min_count, len(tags))))
        for idx, tag in enumerate(tags):
            if tag.tag in rule.protect_tags:
                report.protected.append(tag.reference)
                continue
            if idx in keep_indices:
                report.kept.append(tag.reference)
                continue
            should_delete = False
            if rule.max_age_days is not None and tag.age > timedelta(days=rule.max_age_days):
                should_delete = True
            if rule.max_pulls_threshold is not None and tag.pull_count <= rule.max_pulls_threshold:
                should_delete = True
            if should_delete:
                registry.delete_tag(repository, tag.tag)
                report.deleted.append(tag.reference)
                audit.append(AuditEntry(
                    action=AuditAction.DELETE,
                    actor=actor,
                    timestamp=now,
                    source=registry.name,
                    destination=None,
                    repository=repository,
                    tag=tag.tag,
                    digest=tag.manifest.digest,
                    note="retention policy",
                ))
            else:
                report.kept.append(tag.reference)
    return report


# -- CLI -----------------------------------------------------------------


def _build_default_demo_registry() -> InMemoryRegistry:
    """Seed an in-memory registry with a small dataset for CLI demos."""
    registry = InMemoryRegistry(name="demo.registry", region="local")
    now = datetime.now(timezone.utc)
    for i in range(8):
        registry.seed(
            "ml-service/api",
            f"v1.{i}.0",
            pushed_at=now - timedelta(days=120 - i * 12),
            pull_count=2 if i < 3 else 50,
        )
    registry.seed("ml-service/api", "latest", pull_count=200)
    registry.seed("ml-service/api", "prod", pull_count=180)
    return registry


@click.group()
@click.option("--audit-log", type=click.Path(dir_okay=False),
              help="Append JSONL audit entries to this file")
@click.pass_context
def cli(ctx: click.Context, audit_log: Optional[str]) -> None:
    """Container registry manager."""
    ctx.ensure_object(dict)
    ctx.obj["audit"] = AuditLog(path=Path(audit_log) if audit_log else None)
    ctx.obj["registry"] = _build_default_demo_registry()


@cli.command()
@click.pass_context
def list_tags(ctx: click.Context) -> None:
    """List the seeded demo registry."""
    registry: Registry = ctx.obj["registry"]
    for repo in registry.list_repositories():
        click.echo(f"Repository: {repo}")
        for tag in registry.list_tags(repo):
            click.echo(
                f"  {tag.tag:<10s} "
                f"digest={tag.manifest.digest[:19]}... "
                f"pushed={tag.pushed_at.isoformat(timespec='seconds')} "
                f"pulls={tag.pull_count}"
            )


@cli.command()
@click.option("--repository", required=True)
@click.option("--source-tag", required=True)
@click.option("--target-stage", required=True, type=click.Choice([s.value for s in PromotionStage]))
@click.option("--actor", default="ci")
@click.pass_context
def promote_cmd(
    ctx: click.Context,
    repository: str,
    source_tag: str,
    target_stage: str,
    actor: str,
) -> None:
    """Promote a tag through dev → staging → prod."""
    registry: Registry = ctx.obj["registry"]
    audit: AuditLog = ctx.obj["audit"]
    result = promote(
        registry,
        repository,
        source_tag,
        PromotionStage(target_stage),
        audit,
        actor=actor,
    )
    click.echo(f"Promoted {repository}:{source_tag} → {repository}:{result.to_tag}")
    click.echo(f"  digest={result.digest[:19]}...")


cli.add_command(promote_cmd, name="promote")


@cli.command()
@click.option("--repository", default="*", help="Repository pattern; '*' matches all")
@click.option("--max-age-days", default=90, type=int)
@click.option("--max-pulls-threshold", default=5, type=int)
@click.option("--keep-min-count", default=3, type=int)
@click.pass_context
def retention(
    ctx: click.Context,
    repository: str,
    max_age_days: int,
    max_pulls_threshold: int,
    keep_min_count: int,
) -> None:
    """Apply a retention rule to the in-memory registry."""
    registry: Registry = ctx.obj["registry"]
    audit: AuditLog = ctx.obj["audit"]
    rule = RetentionRule(
        repository_pattern=repository,
        keep_min_count=keep_min_count,
        max_age_days=max_age_days,
        max_pulls_threshold=max_pulls_threshold,
    )
    report = apply_retention(registry, [rule], audit)
    click.echo(f"Retention pass — pattern={repository}")
    click.echo(f"  deleted:   {len(report.deleted)}")
    click.echo(f"  kept:      {len(report.kept)}")
    click.echo(f"  protected: {len(report.protected)}")
    for ref in report.deleted:
        click.echo(f"    - {ref}")


@cli.command()
@click.pass_context
def audit_dump(ctx: click.Context) -> None:
    """Dump audit log to stdout."""
    audit: AuditLog = ctx.obj["audit"]
    for entry in audit.entries:
        click.echo(json.dumps(entry.to_dict()))


cli.add_command(audit_dump, name="audit")


if __name__ == "__main__":
    cli()
