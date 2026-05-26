"""
Validators

Validation helpers used by the DR system to verify configuration shape
and post-restore data integrity.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Optional

from .backup_manager import BackupManager, BackupMetadata, RetentionTier, RETENTION_DAYS
from .recovery_manager import RPO_TARGETS, RTO_TARGETS, ServiceTier


_SERVICE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,61}[a-z0-9]$")
_REGION_RE = re.compile(r"^[a-z]{2,}-[a-z]+-\d+$|^[a-z]+$")  # us-east-1 or "eastus"


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_service_name(name: str) -> ValidationResult:
    result = ValidationResult(valid=True)
    if not _SERVICE_NAME_RE.match(name):
        result.valid = False
        result.errors.append(
            f"Service name {name!r} must be 3-63 chars, "
            "lowercase letters/digits/hyphens, "
            "start with a letter and end alphanumeric."
        )
    return result


def validate_region_pair(primary: str, secondary: str) -> ValidationResult:
    result = ValidationResult(valid=True)
    if not _REGION_RE.match(primary):
        result.errors.append(f"Primary region {primary!r} does not match the expected pattern")
    if not _REGION_RE.match(secondary):
        result.errors.append(f"Secondary region {secondary!r} does not match the expected pattern")
    if primary == secondary:
        result.errors.append("Primary and secondary regions must differ")
    result.valid = not result.errors
    return result


def validate_dr_configuration(
    *,
    services: Dict[str, ServiceTier],
    primary_regions: Dict[str, str],
    secondary_regions: Dict[str, str],
) -> ValidationResult:
    """Validate the cross-service DR config: every service has both regions."""
    result = ValidationResult(valid=True)
    if not services:
        result.valid = False
        result.errors.append("At least one service must be configured")
        return result
    for service in services:
        name_result = validate_service_name(service)
        if not name_result.valid:
            result.errors.extend(name_result.errors)
        if service not in primary_regions:
            result.errors.append(f"Service {service!r} is missing primary_regions entry")
        if service not in secondary_regions:
            result.errors.append(f"Service {service!r} is missing secondary_regions entry")
        if service in primary_regions and service in secondary_regions:
            region_result = validate_region_pair(
                primary_regions[service], secondary_regions[service]
            )
            if not region_result.valid:
                result.errors.extend(region_result.errors)
    result.valid = not result.errors
    return result


def validate_payload_checksum(payload: bytes, expected_checksum: str) -> ValidationResult:
    """Compare a payload against a previously recorded SHA-256."""
    result = ValidationResult(valid=True)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_checksum:
        result.valid = False
        result.errors.append(
            f"Checksum mismatch: expected {expected_checksum[:16]}…, got {actual[:16]}…"
        )
    return result


def validate_backup_metadata(metadata: BackupMetadata) -> ValidationResult:
    """Sanity-check a BackupMetadata instance after restore."""
    result = ValidationResult(valid=True)
    if metadata.size_bytes <= 0:
        result.errors.append("Backup size must be positive")
    if metadata.retention_tier not in RETENTION_DAYS:
        result.errors.append(f"Unknown retention tier: {metadata.retention_tier!r}")
    if metadata.backup_type.value == "incremental" and metadata.parent_backup_id is None:
        result.errors.append("Incremental backup is missing parent_backup_id")
    if not metadata.checksum_sha256 or len(metadata.checksum_sha256) != 64:
        result.errors.append("Checksum field is not a 64-char SHA-256 hex")
    result.valid = not result.errors
    return result


def validate_rto_target(
    achieved: timedelta,
    tier: ServiceTier,
) -> ValidationResult:
    target = RTO_TARGETS[tier]
    if achieved <= target:
        return ValidationResult(valid=True)
    return ValidationResult(
        valid=False,
        errors=[
            f"Achieved RTO {achieved.total_seconds():.1f}s exceeds "
            f"{tier.value} target of {target.total_seconds():.0f}s"
        ],
    )


def validate_rpo_target(
    achieved: timedelta,
    tier: ServiceTier,
) -> ValidationResult:
    target = RPO_TARGETS[tier]
    if achieved <= target:
        return ValidationResult(valid=True)
    return ValidationResult(
        valid=False,
        errors=[
            f"Achieved RPO {achieved.total_seconds():.1f}s exceeds "
            f"{tier.value} target of {target.total_seconds():.0f}s"
        ],
    )


def validate_backup_inventory(
    backup_manager: BackupManager,
    *,
    minimum_per_tier: Optional[Dict[RetentionTier, int]] = None,
) -> ValidationResult:
    """Ensure the inventory has at least N backups per retention tier."""
    minimum = minimum_per_tier or {RetentionTier.DAILY: 1}
    result = ValidationResult(valid=True)
    backups = backup_manager.list_backups()
    counts: Dict[RetentionTier, int] = {tier: 0 for tier in RetentionTier}
    for backup in backups:
        counts[backup.retention_tier] += 1
    for tier, required in minimum.items():
        if counts[tier] < required:
            result.errors.append(
                f"Tier {tier.value}: {counts[tier]} backups (need >= {required})"
            )
    if not backups:
        result.warnings.append("Backup inventory is empty")
    result.valid = not result.errors
    return result
