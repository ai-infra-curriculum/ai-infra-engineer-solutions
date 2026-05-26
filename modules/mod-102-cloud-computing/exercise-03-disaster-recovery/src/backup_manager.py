"""
Backup Manager

Encrypted, retention-aware backup management for ML infrastructure.
Supports multiple backup sources (etcd, persistent volumes, databases,
configurations, container images), incremental + full backups, and
cross-region replication via a pluggable storage backend.

The storage backend is a Protocol so callers can wire in S3, GCS, Azure
Blob, or a local filesystem (used by tests). The default LocalStorage
backend is suitable for development and CI; cloud-specific subclasses
can replace it without touching the BackupManager itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol

logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class BackupSource(str, Enum):
    ETCD = "etcd"
    PERSISTENT_VOLUME = "persistent_volume"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    CONTAINER_IMAGE = "container_image"


class RetentionTier(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


RETENTION_DAYS: Dict[RetentionTier, int] = {
    RetentionTier.DAILY: 7,
    RetentionTier.WEEKLY: 30,
    RetentionTier.MONTHLY: 90,
    RetentionTier.YEARLY: 365,
}


@dataclass
class BackupMetadata:
    """Metadata describing a single backup artifact."""

    backup_id: str
    source: BackupSource
    backup_type: BackupType
    retention_tier: RetentionTier
    size_bytes: int
    checksum_sha256: str
    encrypted: bool
    created_at: datetime
    region: str
    replicated_regions: List[str] = field(default_factory=list)
    parent_backup_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    def expires_at(self) -> datetime:
        return self.created_at + timedelta(days=RETENTION_DAYS[self.retention_tier])

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now >= self.expires_at()


class StorageBackend(Protocol):
    """Pluggable storage backend used by BackupManager."""

    region: str

    def write(self, key: str, data: bytes) -> int: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def list(self, prefix: str = "") -> Iterable[str]: ...

    def copy_to(self, key: str, destination: "StorageBackend") -> int: ...


class LocalStorageBackend:
    """Filesystem-backed storage implementation used in tests + dev."""

    def __init__(self, root: Path, region: str = "local"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.region = region

    def _path(self, key: str) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write(self, key: str, data: bytes) -> int:
        path = self._path(key)
        path.write_bytes(data)
        return len(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def list(self, prefix: str = "") -> Iterable[str]:
        for entry in self.root.rglob("*"):
            if entry.is_file():
                rel = str(entry.relative_to(self.root))
                if rel.startswith(prefix):
                    yield rel

    def copy_to(self, key: str, destination: "StorageBackend") -> int:
        return destination.write(key, self.read(key))


# Marker prepended to encrypted payloads in the demo cipher. A real
# implementation would call KMS/Key Vault and AES-GCM. The demo cipher
# preserves the property "encrypted output != plaintext" and survives a
# round-trip, which is what the integration tests assert.
_DEMO_ENCRYPTION_KEY = b"ml-infra-demo-key"
_DEMO_HEADER = b"DEMO-ENC:v1\n"


def _demo_encrypt(payload: bytes, key: bytes = _DEMO_ENCRYPTION_KEY) -> bytes:
    body = bytes(b ^ key[i % len(key)] for i, b in enumerate(payload))
    return _DEMO_HEADER + body


def _demo_decrypt(payload: bytes, key: bytes = _DEMO_ENCRYPTION_KEY) -> bytes:
    if not payload.startswith(_DEMO_HEADER):
        raise ValueError("Payload is not encrypted with the demo cipher")
    body = payload[len(_DEMO_HEADER):]
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(body))


class BackupManager:
    """Orchestrates backups across sources and storage backends."""

    def __init__(
        self,
        primary_storage: StorageBackend,
        replica_storage: Optional[StorageBackend] = None,
        *,
        encrypt: bool = True,
        manifest_path: Optional[Path] = None,
    ):
        self.primary = primary_storage
        self.replica = replica_storage
        self.encrypt = encrypt
        self.manifest_path = manifest_path
        self._metadata: Dict[str, BackupMetadata] = {}
        if manifest_path is not None and manifest_path.exists():
            self._load_manifest()

    def backup(
        self,
        source: BackupSource,
        payload: bytes,
        *,
        backup_type: BackupType = BackupType.FULL,
        retention_tier: RetentionTier = RetentionTier.DAILY,
        parent_backup_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        now: Optional[datetime] = None,
    ) -> BackupMetadata:
        """Create a backup artifact and persist it to primary storage."""
        if backup_type is BackupType.INCREMENTAL and parent_backup_id is None:
            raise ValueError("Incremental backups require a parent_backup_id")
        if parent_backup_id and parent_backup_id not in self._metadata:
            raise ValueError(f"Unknown parent backup: {parent_backup_id}")

        now = now or datetime.now(timezone.utc)
        backup_id = self._generate_id(source, now)
        body = _demo_encrypt(payload) if self.encrypt else payload
        checksum = hashlib.sha256(payload).hexdigest()
        size = self.primary.write(self._key(backup_id, source), body)

        metadata = BackupMetadata(
            backup_id=backup_id,
            source=source,
            backup_type=backup_type,
            retention_tier=retention_tier,
            size_bytes=size,
            checksum_sha256=checksum,
            encrypted=self.encrypt,
            created_at=now,
            region=self.primary.region,
            parent_backup_id=parent_backup_id,
            tags=tags or {},
        )
        self._metadata[backup_id] = metadata
        self._persist_manifest()
        logger.info("Backup %s created (%s, %d bytes)", backup_id, source.value, size)
        return metadata

    def restore(self, backup_id: str) -> bytes:
        """Read + decrypt + verify a backup, returning the original payload."""
        metadata = self._metadata.get(backup_id)
        if metadata is None:
            raise KeyError(f"Unknown backup: {backup_id}")
        body = self.primary.read(self._key(backup_id, metadata.source))
        payload = _demo_decrypt(body) if metadata.encrypted else body
        actual_checksum = hashlib.sha256(payload).hexdigest()
        if actual_checksum != metadata.checksum_sha256:
            raise RuntimeError(
                f"Checksum mismatch for {backup_id}: "
                f"expected {metadata.checksum_sha256}, got {actual_checksum}"
            )
        return payload

    def replicate(self, backup_id: str) -> None:
        """Copy a backup to the configured replica storage."""
        if self.replica is None:
            raise RuntimeError("No replica storage configured")
        metadata = self._metadata.get(backup_id)
        if metadata is None:
            raise KeyError(f"Unknown backup: {backup_id}")
        key = self._key(backup_id, metadata.source)
        self.primary.copy_to(key, self.replica)
        if self.replica.region not in metadata.replicated_regions:
            metadata.replicated_regions.append(self.replica.region)
        self._persist_manifest()
        logger.info("Backup %s replicated to %s", backup_id, self.replica.region)

    def list_backups(
        self,
        source: Optional[BackupSource] = None,
        retention_tier: Optional[RetentionTier] = None,
    ) -> List[BackupMetadata]:
        return [
            m
            for m in self._metadata.values()
            if (source is None or m.source is source)
            and (retention_tier is None or m.retention_tier is retention_tier)
        ]

    def get(self, backup_id: str) -> BackupMetadata:
        if backup_id not in self._metadata:
            raise KeyError(f"Unknown backup: {backup_id}")
        return self._metadata[backup_id]

    def prune_expired(self, now: Optional[datetime] = None) -> List[str]:
        """Delete backups past their retention horizon. Returns removed IDs."""
        now = now or datetime.now(timezone.utc)
        removed: List[str] = []
        for backup_id, metadata in list(self._metadata.items()):
            if metadata.is_expired(now):
                self.primary.delete(self._key(backup_id, metadata.source))
                if self.replica is not None:
                    try:
                        self.replica.delete(self._key(backup_id, metadata.source))
                    except Exception:  # pragma: no cover - best effort
                        logger.warning("Failed to prune replica copy of %s", backup_id)
                self._metadata.pop(backup_id)
                removed.append(backup_id)
        if removed:
            self._persist_manifest()
            logger.info("Pruned %d expired backups", len(removed))
        return removed

    def to_json(self) -> str:
        """Serialize the metadata index (suitable for a manifest file)."""
        items = []
        for metadata in self._metadata.values():
            items.append({
                "backup_id": metadata.backup_id,
                "source": metadata.source.value,
                "backup_type": metadata.backup_type.value,
                "retention_tier": metadata.retention_tier.value,
                "size_bytes": metadata.size_bytes,
                "checksum_sha256": metadata.checksum_sha256,
                "encrypted": metadata.encrypted,
                "created_at": metadata.created_at.isoformat(),
                "region": metadata.region,
                "replicated_regions": list(metadata.replicated_regions),
                "parent_backup_id": metadata.parent_backup_id,
                "tags": dict(metadata.tags),
            })
        return json.dumps({"backups": items}, indent=2)

    # -- internals -----------------------------------------------------

    def _persist_manifest(self) -> None:
        if self.manifest_path is None:
            return
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(self.to_json())

    def _load_manifest(self) -> None:
        assert self.manifest_path is not None
        data = json.loads(self.manifest_path.read_text())
        for item in data.get("backups", []):
            metadata = BackupMetadata(
                backup_id=item["backup_id"],
                source=BackupSource(item["source"]),
                backup_type=BackupType(item["backup_type"]),
                retention_tier=RetentionTier(item["retention_tier"]),
                size_bytes=item["size_bytes"],
                checksum_sha256=item["checksum_sha256"],
                encrypted=item["encrypted"],
                created_at=datetime.fromisoformat(item["created_at"]),
                region=item["region"],
                replicated_regions=list(item.get("replicated_regions", [])),
                parent_backup_id=item.get("parent_backup_id"),
                tags=dict(item.get("tags", {})),
            )
            self._metadata[metadata.backup_id] = metadata

    @staticmethod
    def _generate_id(source: BackupSource, now: datetime) -> str:
        nonce = os.urandom(4).hex()
        return f"{source.value}-{now.strftime('%Y%m%dT%H%M%S')}-{nonce}"

    @staticmethod
    def _key(backup_id: str, source: BackupSource) -> str:
        return f"backups/{source.value}/{backup_id}.bin"
