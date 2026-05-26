"""Tests for the recovery manager + validators."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from src.backup_manager import (
    BackupManager,
    BackupSource,
    LocalStorageBackend,
    RetentionTier,
)
from src.recovery_manager import (
    FailoverStatus,
    HealthCheckResult,
    RPO_TARGETS,
    RTO_TARGETS,
    RecoveryManager,
    ServiceTier,
)
from src.validators import (
    validate_backup_inventory,
    validate_backup_metadata,
    validate_dr_configuration,
    validate_payload_checksum,
    validate_region_pair,
    validate_rpo_target,
    validate_rto_target,
    validate_service_name,
)


@pytest.fixture
def manager(tmp_path: Path) -> BackupManager:
    primary = LocalStorageBackend(root=tmp_path / "primary", region="us-east-1")
    replica = LocalStorageBackend(root=tmp_path / "replica", region="us-west-2")
    return BackupManager(primary, replica_storage=replica)


class _ScriptedHealth:
    """Health check that returns a scripted sequence of results."""

    def __init__(self, responses: List[bool]):
        self.responses = list(responses)
        self.index = 0

    def check(self, service: str) -> HealthCheckResult:
        healthy = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return HealthCheckResult(
            service=service,
            healthy=healthy,
            response_time_ms=10.0,
            error=None if healthy else "synthetic failure",
        )


class TestRecoveryManager:
    def test_failover_triggers_after_three_failures(self, manager: BackupManager):
        health = _ScriptedHealth([False, False, False, False])
        events = []
        recovery = RecoveryManager(manager, health, notify=lambda k, p: events.append(k))
        recovery.register_service("api", ServiceTier.CRITICAL, "us-east-1", "us-west-2")
        # First evaluation triggers all three "failure" results in a row.
        for _ in range(3):
            recovery.evaluate_health()
        state = recovery.services["api"]
        assert state.status is FailoverStatus.FAILED_OVER
        assert recovery.failover_history
        assert recovery.failover_history[0].success is True
        assert "failover_completed" in events

    def test_no_failover_on_single_failure(self, manager: BackupManager):
        health = _ScriptedHealth([False, True])
        recovery = RecoveryManager(manager, health)
        recovery.register_service("api", ServiceTier.HIGH, "us-east-1", "us-west-2")
        recovery.evaluate_health()  # consecutive_failures = 1
        recovery.evaluate_health()  # healthy → reset
        state = recovery.services["api"]
        assert state.status is FailoverStatus.PRIMARY
        assert state.consecutive_failures == 0

    def test_recovery_emits_when_returning_to_health(self, manager: BackupManager):
        health = _ScriptedHealth([False, True])
        topics: List[str] = []
        recovery = RecoveryManager(manager, health, notify=lambda k, p: topics.append(k))
        recovery.register_service("api", ServiceTier.HIGH, "us-east-1", "us-west-2")
        recovery.evaluate_health()
        recovery.evaluate_health()
        assert "degraded" in topics
        assert "recovered" in topics

    def test_restore_uses_latest_backup_for_source(self, manager: BackupManager):
        old = manager.backup(
            BackupSource.DATABASE, b"OLD",
            now=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        new = manager.backup(
            BackupSource.DATABASE, b"NEW",
            now=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        recovery = RecoveryManager(manager, _ScriptedHealth([True]))
        payload = recovery.restore(BackupSource.DATABASE)
        assert payload == b"NEW"

    def test_point_in_time_restore_picks_appropriate_backup(self, manager: BackupManager):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        manager.backup(
            BackupSource.DATABASE, b"OLDER",
            now=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        manager.backup(
            BackupSource.DATABASE, b"NEWER",
            now=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        recovery = RecoveryManager(manager, _ScriptedHealth([True]))
        payload = recovery.restore(BackupSource.DATABASE, target_time=cutoff)
        assert payload == b"OLDER"

    def test_restore_with_no_backups_raises(self, manager: BackupManager):
        recovery = RecoveryManager(manager, _ScriptedHealth([True]))
        with pytest.raises(LookupError):
            recovery.restore(BackupSource.DATABASE)

    def test_drill_meets_targets_for_small_payload(self, manager: BackupManager):
        manager.backup(BackupSource.DATABASE, b"payload")
        recovery = RecoveryManager(manager, _ScriptedHealth([True]))
        recovery.register_service("api", ServiceTier.CRITICAL, "us-east-1", "us-west-2")
        result = recovery.run_drill("api", BackupSource.DATABASE)
        assert result.rto_met is True  # local restore is fast
        # Just-created backup; RPO should be near zero.
        assert result.achieved_rpo < RPO_TARGETS[ServiceTier.CRITICAL]

    def test_drill_unknown_service_raises(self, manager: BackupManager):
        recovery = RecoveryManager(manager, _ScriptedHealth([True]))
        with pytest.raises(KeyError):
            recovery.run_drill("missing", BackupSource.DATABASE)


class TestValidators:
    @pytest.mark.parametrize("name,valid", [
        ("api-service", True),
        ("svc", True),
        ("API-svc", False),
        ("with_underscore", False),
        ("trailing-", False),
        ("a", False),
        ("1starts-with-digit", False),
    ])
    def test_service_name(self, name: str, valid: bool):
        result = validate_service_name(name)
        assert result.valid is valid

    def test_region_pair_must_differ(self):
        result = validate_region_pair("us-east-1", "us-east-1")
        assert not result.valid

    def test_region_pair_accepts_aws_and_azure_shapes(self):
        assert validate_region_pair("us-east-1", "us-west-2").valid
        assert validate_region_pair("eastus", "westeurope").valid

    def test_dr_configuration_requires_all_services(self):
        result = validate_dr_configuration(
            services={"api": ServiceTier.CRITICAL},
            primary_regions={"api": "us-east-1"},
            secondary_regions={},
        )
        assert not result.valid
        assert any("secondary_regions" in e for e in result.errors)

    def test_payload_checksum_round_trip(self):
        import hashlib
        payload = b"hello"
        cs = hashlib.sha256(payload).hexdigest()
        assert validate_payload_checksum(payload, cs).valid
        assert not validate_payload_checksum(payload, "0" * 64).valid

    def test_backup_metadata_valid(self, manager: BackupManager):
        metadata = manager.backup(BackupSource.DATABASE, b"x")
        assert validate_backup_metadata(metadata).valid

    def test_rto_validator(self):
        ok = validate_rto_target(timedelta(seconds=10), ServiceTier.CRITICAL)
        fail = validate_rto_target(timedelta(hours=2), ServiceTier.CRITICAL)
        assert ok.valid
        assert not fail.valid

    def test_rpo_validator(self):
        ok = validate_rpo_target(timedelta(seconds=10), ServiceTier.HIGH)
        fail = validate_rpo_target(timedelta(hours=1), ServiceTier.HIGH)
        assert ok.valid
        assert not fail.valid

    def test_inventory_warns_when_empty(self, manager: BackupManager):
        result = validate_backup_inventory(manager)
        assert "empty" in " ".join(result.warnings)

    def test_inventory_meets_minimums(self, manager: BackupManager):
        manager.backup(BackupSource.DATABASE, b"x")
        result = validate_backup_inventory(
            manager,
            minimum_per_tier={RetentionTier.DAILY: 1},
        )
        assert result.valid
