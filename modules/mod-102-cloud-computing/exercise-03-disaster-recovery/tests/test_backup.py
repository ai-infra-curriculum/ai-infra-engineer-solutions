"""Tests for the backup manager + storage backends."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.backup_manager import (
    BackupManager,
    BackupSource,
    BackupType,
    LocalStorageBackend,
    RetentionTier,
    _demo_decrypt,
    _demo_encrypt,
)


@pytest.fixture
def primary(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(root=tmp_path / "primary", region="us-east-1")


@pytest.fixture
def replica(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(root=tmp_path / "replica", region="us-west-2")


@pytest.fixture
def manager(primary, replica) -> BackupManager:
    return BackupManager(primary, replica_storage=replica)


PAYLOAD = b"the quick brown fox " * 64


class TestLocalStorageBackend:
    def test_write_then_read_round_trip(self, primary):
        primary.write("data/x", b"hello")
        assert primary.read("data/x") == b"hello"

    def test_list_returns_relative_keys(self, primary):
        primary.write("a/b/c", b"1")
        primary.write("a/d", b"2")
        keys = sorted(primary.list())
        assert "a/b/c" in keys
        assert "a/d" in keys

    def test_delete_removes_file(self, primary):
        primary.write("temp", b"x")
        primary.delete("temp")
        with pytest.raises(FileNotFoundError):
            primary.read("temp")

    def test_copy_to_replicates_content(self, primary, replica):
        primary.write("k", b"copyme")
        bytes_copied = primary.copy_to("k", replica)
        assert bytes_copied == len(b"copyme")
        assert replica.read("k") == b"copyme"


class TestDemoEncryption:
    def test_round_trip(self):
        original = b"secret data"
        encrypted = _demo_encrypt(original)
        assert encrypted != original
        assert _demo_decrypt(encrypted) == original

    def test_decrypt_rejects_unencrypted_payload(self):
        with pytest.raises(ValueError):
            _demo_decrypt(b"plain text")


class TestBackupManager:
    def test_full_backup_round_trip(self, manager: BackupManager):
        metadata = manager.backup(BackupSource.DATABASE, PAYLOAD)
        assert metadata.backup_type is BackupType.FULL
        assert metadata.encrypted is True
        assert metadata.size_bytes > len(PAYLOAD)  # encrypted header + body
        restored = manager.restore(metadata.backup_id)
        assert restored == PAYLOAD

    def test_unencrypted_backup_round_trip(self, primary):
        manager = BackupManager(primary, encrypt=False)
        metadata = manager.backup(BackupSource.CONFIGURATION, b"raw")
        assert metadata.encrypted is False
        assert manager.restore(metadata.backup_id) == b"raw"

    def test_incremental_requires_parent(self, manager: BackupManager):
        with pytest.raises(ValueError):
            manager.backup(BackupSource.ETCD, PAYLOAD, backup_type=BackupType.INCREMENTAL)

    def test_incremental_chains_to_parent(self, manager: BackupManager):
        parent = manager.backup(BackupSource.ETCD, PAYLOAD)
        child = manager.backup(
            BackupSource.ETCD,
            PAYLOAD + b"-delta",
            backup_type=BackupType.INCREMENTAL,
            parent_backup_id=parent.backup_id,
        )
        assert child.parent_backup_id == parent.backup_id

    def test_replication_records_destination_region(self, manager: BackupManager):
        metadata = manager.backup(BackupSource.DATABASE, PAYLOAD)
        manager.replicate(metadata.backup_id)
        refreshed = manager.get(metadata.backup_id)
        assert "us-west-2" in refreshed.replicated_regions

    def test_replication_idempotent(self, manager: BackupManager):
        metadata = manager.backup(BackupSource.DATABASE, PAYLOAD)
        manager.replicate(metadata.backup_id)
        manager.replicate(metadata.backup_id)
        refreshed = manager.get(metadata.backup_id)
        assert refreshed.replicated_regions.count("us-west-2") == 1

    def test_replication_without_replica_storage_raises(self, primary):
        manager = BackupManager(primary)
        metadata = manager.backup(BackupSource.DATABASE, PAYLOAD)
        with pytest.raises(RuntimeError):
            manager.replicate(metadata.backup_id)

    def test_checksum_mismatch_detected_on_restore(self, manager: BackupManager):
        metadata = manager.backup(BackupSource.DATABASE, PAYLOAD)
        # Corrupt the persisted object.
        key = BackupManager._key(metadata.backup_id, metadata.source)
        manager.primary.write(key, b"DEMO-ENC:v1\nGARBAGE")
        with pytest.raises(RuntimeError, match="Checksum mismatch"):
            manager.restore(metadata.backup_id)

    def test_list_filters_by_source_and_tier(self, manager: BackupManager):
        manager.backup(BackupSource.DATABASE, b"a", retention_tier=RetentionTier.DAILY)
        manager.backup(BackupSource.DATABASE, b"b", retention_tier=RetentionTier.WEEKLY)
        manager.backup(BackupSource.ETCD, b"c", retention_tier=RetentionTier.DAILY)
        databases = manager.list_backups(source=BackupSource.DATABASE)
        assert len(databases) == 2
        weeklies = manager.list_backups(retention_tier=RetentionTier.WEEKLY)
        assert len(weeklies) == 1

    def test_prune_expired_removes_old_backups(self, manager: BackupManager):
        long_ago = datetime.now(timezone.utc) - timedelta(days=400)
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        old = manager.backup(BackupSource.DATABASE, b"old", retention_tier=RetentionTier.DAILY, now=long_ago)
        new = manager.backup(BackupSource.DATABASE, b"new", retention_tier=RetentionTier.DAILY, now=recent)
        removed = manager.prune_expired()
        assert old.backup_id in removed
        assert new.backup_id not in removed
        assert manager.get(new.backup_id)
        with pytest.raises(KeyError):
            manager.get(old.backup_id)

    def test_manifest_to_json_includes_all_backups(self, manager: BackupManager):
        manager.backup(BackupSource.DATABASE, b"a")
        manager.backup(BackupSource.ETCD, b"b")
        import json
        manifest = json.loads(manager.to_json())
        assert len(manifest["backups"]) == 2
