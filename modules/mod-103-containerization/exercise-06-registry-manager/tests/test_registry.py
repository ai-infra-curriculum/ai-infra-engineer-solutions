"""Tests for the registry manager."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.main import (
    AuditAction,
    AuditLog,
    PromotionStage,
    apply_retention,
    promote,
    sync_repository,
    sync_tag,
)
from src.registry.acr import ACRRegistry
from src.registry.base import (
    ImageManifest,
    ImageTag,
    InMemoryRegistry,
    Registry,
    RegistryError,
    RetentionRule,
)
from src.registry.ecr import ECRRegistry
from src.registry.gcr import GCRRegistry


@pytest.fixture
def src_registry() -> InMemoryRegistry:
    reg = InMemoryRegistry(name="source", region="us-east-1")
    reg.seed("ml/api", "v1.0", pushed_at=datetime.now(timezone.utc) - timedelta(days=10))
    reg.seed("ml/api", "v1.1", pushed_at=datetime.now(timezone.utc) - timedelta(days=5))
    reg.seed("ml/api", "latest")
    return reg


@pytest.fixture
def dst_registry() -> InMemoryRegistry:
    return InMemoryRegistry(name="destination", region="eu-west-1")


class TestInMemoryRegistry:
    def test_seed_and_get(self, src_registry: InMemoryRegistry):
        tag = src_registry.get_tag("ml/api", "v1.0")
        assert tag.repository == "ml/api"
        assert tag.tag == "v1.0"
        assert tag.manifest.digest.startswith("sha256:")

    def test_list_tags_sorted_by_pushed_desc(self, src_registry: InMemoryRegistry):
        tags = src_registry.list_tags("ml/api")
        assert [t.tag for t in tags][0] == "latest"  # most-recent seed

    def test_push_creates_record(self, dst_registry: InMemoryRegistry):
        manifest = ImageManifest(digest="sha256:abc", size_bytes=10)
        record = dst_registry.push("ml/api", "v2.0", manifest)
        assert record.tag == "v2.0"
        assert dst_registry.list_repositories() == ["ml/api"]

    def test_delete_unknown_raises(self, dst_registry: InMemoryRegistry):
        with pytest.raises(RegistryError):
            dst_registry.delete_tag("ml/api", "nope")

    def test_record_pull_increments_counter(self, src_registry: InMemoryRegistry):
        src_registry.record_pull("ml/api", "v1.0")
        assert src_registry.get_tag("ml/api", "v1.0").pull_count == 1
        assert src_registry.get_tag("ml/api", "v1.0").last_pulled_at is not None


class TestSync:
    def test_sync_tag_copies_when_destination_lacks_tag(
        self, src_registry: InMemoryRegistry, dst_registry: InMemoryRegistry,
    ):
        audit = AuditLog()
        report = sync_tag(src_registry, dst_registry, "ml/api", "v1.0", audit)
        assert "ml/api:v1.0" in report.copied
        assert not report.skipped_same_digest
        # The audit log records the sync.
        assert audit.entries
        assert audit.entries[0].action is AuditAction.SYNC

    def test_sync_tag_skips_when_destination_has_matching_digest(
        self, src_registry: InMemoryRegistry, dst_registry: InMemoryRegistry,
    ):
        audit = AuditLog()
        sync_tag(src_registry, dst_registry, "ml/api", "v1.0", audit)
        report = sync_tag(src_registry, dst_registry, "ml/api", "v1.0", audit)
        assert "ml/api:v1.0" in report.skipped_same_digest
        assert len(audit.entries) == 1  # second call didn't record

    def test_sync_repository_copies_all_tags(
        self, src_registry: InMemoryRegistry, dst_registry: InMemoryRegistry,
    ):
        audit = AuditLog()
        reports = sync_repository(src_registry, [dst_registry], "ml/api", audit)
        assert dst_registry.name in reports
        assert len(reports[dst_registry.name].copied) == 3
        assert len(dst_registry.list_tags("ml/api")) == 3

    def test_sync_repository_to_multiple_destinations(
        self, src_registry: InMemoryRegistry,
    ):
        d1 = InMemoryRegistry(name="d1", region="eu-west-1")
        d2 = InMemoryRegistry(name="d2", region="ap-southeast-1")
        audit = AuditLog()
        reports = sync_repository(src_registry, [d1, d2], "ml/api", audit)
        assert "d1" in reports and "d2" in reports
        assert len(d1.list_tags("ml/api")) == 3
        assert len(d2.list_tags("ml/api")) == 3

    def test_audit_log_to_file(
        self, src_registry: InMemoryRegistry, dst_registry: InMemoryRegistry,
        tmp_path: Path,
    ):
        log_path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=log_path)
        sync_tag(src_registry, dst_registry, "ml/api", "v1.0", audit)
        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        import json
        record = json.loads(lines[0])
        assert record["action"] == "sync"


class TestPromotion:
    def test_promote_to_staging_creates_tag(self, src_registry: InMemoryRegistry):
        audit = AuditLog()
        result = promote(src_registry, "ml/api", "v1.1", PromotionStage.STAGING, audit, actor="alice")
        assert result.to_tag == "staging"
        assert src_registry.get_tag("ml/api", "staging").manifest.digest == result.digest

    def test_promote_to_prod_creates_tag(self, src_registry: InMemoryRegistry):
        audit = AuditLog()
        result = promote(src_registry, "ml/api", "v1.1", PromotionStage.PROD, audit, actor="alice")
        assert result.to_tag == "prod"

    def test_promote_records_audit_entry(self, src_registry: InMemoryRegistry):
        audit = AuditLog()
        promote(src_registry, "ml/api", "v1.0", PromotionStage.STAGING, audit, actor="bob")
        entry = audit.entries[0]
        assert entry.action is AuditAction.PROMOTE
        assert entry.actor == "bob"
        assert "promoted from v1.0" in entry.note

    def test_promote_denied_when_approver_rejects(self, src_registry: InMemoryRegistry):
        audit = AuditLog()
        with pytest.raises(PermissionError):
            promote(
                src_registry, "ml/api", "v1.0", PromotionStage.PROD, audit,
                approver=lambda *args: False,
            )

    def test_promote_preserves_source_digest(self, src_registry: InMemoryRegistry):
        audit = AuditLog()
        source = src_registry.get_tag("ml/api", "v1.0")
        result = promote(src_registry, "ml/api", "v1.0", PromotionStage.STAGING, audit)
        assert result.digest == source.manifest.digest


class TestRetention:
    def test_deletes_old_unused_tags(self):
        registry = InMemoryRegistry(name="r", region="us-east-1")
        now = datetime.now(timezone.utc)
        for i in range(6):
            registry.seed(
                "ml/api",
                f"v{i}",
                pushed_at=now - timedelta(days=180),
                pull_count=2,
            )
        rule = RetentionRule(
            repository_pattern="ml/*",
            keep_min_count=2,
            max_age_days=90,
            max_pulls_threshold=5,
        )
        report = apply_retention(registry, [rule], AuditLog())
        assert len(report.deleted) == 4  # 6 seeded - 2 keep_min_count
        # 2 most-recent kept.
        assert len(registry.list_tags("ml/api")) == 2

    def test_does_not_delete_protected_tags(self):
        registry = InMemoryRegistry(name="r", region="us-east-1")
        now = datetime.now(timezone.utc)
        registry.seed("ml/api", "latest", pushed_at=now - timedelta(days=365), pull_count=0)
        registry.seed("ml/api", "old", pushed_at=now - timedelta(days=365), pull_count=0)
        rule = RetentionRule(
            repository_pattern="ml/*",
            keep_min_count=0,
            max_age_days=90,
            max_pulls_threshold=5,
        )
        report = apply_retention(registry, [rule], AuditLog())
        assert "ml/api:latest" in report.protected
        assert "ml/api:old" in report.deleted

    def test_skips_repos_with_no_matching_rule(self):
        registry = InMemoryRegistry(name="r", region="us-east-1")
        now = datetime.now(timezone.utc)
        registry.seed("infra/db", "v1", pushed_at=now - timedelta(days=365), pull_count=0)
        rule = RetentionRule(repository_pattern="ml/*", max_age_days=10)
        report = apply_retention(registry, [rule], AuditLog())
        # Infra repo retained because no rule matches.
        assert "infra/db:v1" in report.kept
        assert not report.deleted

    def test_audit_records_each_deletion(self):
        registry = InMemoryRegistry(name="r", region="us-east-1")
        now = datetime.now(timezone.utc)
        for i in range(3):
            registry.seed("ml/api", f"v{i}", pushed_at=now - timedelta(days=180), pull_count=0)
        audit = AuditLog()
        rule = RetentionRule(
            repository_pattern="*",
            keep_min_count=0,
            max_age_days=90,
            max_pulls_threshold=5,
        )
        apply_retention(registry, [rule], audit)
        delete_entries = [e for e in audit.entries if e.action is AuditAction.DELETE]
        assert len(delete_entries) == 3


class TestProviderSubclasses:
    def test_ecr_default_path_uses_in_memory(self):
        ecr = ECRRegistry(account_id="123456789012", region="us-east-1")
        assert ecr.provider == "ecr"
        assert ecr.is_live is False
        assert "123456789012.dkr.ecr.us-east-1.amazonaws.com" in ecr.name

    def test_gcr_uses_legacy_host_for_us(self):
        gcr = GCRRegistry(project_id="my-project", region="us")
        assert "us.gcr.io/my-project" in gcr.name

    def test_gcr_uses_artifact_registry_host_for_specific_region(self):
        gcr = GCRRegistry(project_id="my-project", region="us-central1")
        assert "us-central1-docker.pkg.dev/my-project" in gcr.name

    def test_acr_constructs_expected_host(self):
        acr = ACRRegistry(registry_name="myreg", region="eastus")
        assert acr.name == "myreg.azurecr.io"
        assert acr.region == "eastus"

    def test_concrete_registries_support_sync(self):
        # Sync between heterogeneous providers using their in-memory paths.
        ecr = ECRRegistry(account_id="123", region="us-east-1")
        gcr = GCRRegistry(project_id="project", region="us")
        ecr.seed("ml/api", "v1.0")
        audit = AuditLog()
        sync_tag(ecr, gcr, "ml/api", "v1.0", audit)
        assert gcr.get_tag("ml/api", "v1.0").manifest.digest == ecr.get_tag("ml/api", "v1.0").manifest.digest


class TestAuditLog:
    def test_filter_by_action(self):
        audit = AuditLog()
        audit.append_dummy = lambda *args: None  # type: ignore[attr-defined]
        # Use the public API via promote().
        registry = InMemoryRegistry(name="r", region="us-east-1")
        registry.seed("ml/api", "v1.0")
        promote(registry, "ml/api", "v1.0", PromotionStage.STAGING, audit)
        sync_tag(registry, InMemoryRegistry(name="d", region="us-west-2"),
                 "ml/api", "v1.0", audit)
        promotes = audit.filter(action=AuditAction.PROMOTE)
        syncs = audit.filter(action=AuditAction.SYNC)
        assert len(promotes) == 1
        assert len(syncs) == 1
