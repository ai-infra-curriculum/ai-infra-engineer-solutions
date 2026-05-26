"""
Recovery Manager

Coordinates the disaster-recovery side of the system:
- Health checks against monitored services with consecutive-failure
  thresholds.
- Automatic failover when an unhealthy primary is detected.
- Restore orchestration (point-in-time recovery using backup metadata).
- DR drills that measure achieved RTO + RPO against targets.
- A notification hook callers wire into PagerDuty / Slack / email.

The recovery manager talks to the backup manager via its public API
(get / restore / list_backups). It does not write to backup storage
directly.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional, Protocol

from .backup_manager import (
    BackupManager,
    BackupMetadata,
    BackupSource,
    RetentionTier,
)

logger = logging.getLogger(__name__)


class ServiceTier(str, Enum):
    """SLA tier; determines RTO/RPO commitments."""

    CRITICAL = "critical"  # RTO < 1h,  RPO < 5m
    HIGH = "high"  # RTO < 4h,  RPO < 15m
    STANDARD = "standard"  # RTO < 24h, RPO < 1h


RTO_TARGETS: Dict[ServiceTier, timedelta] = {
    ServiceTier.CRITICAL: timedelta(hours=1),
    ServiceTier.HIGH: timedelta(hours=4),
    ServiceTier.STANDARD: timedelta(hours=24),
}

RPO_TARGETS: Dict[ServiceTier, timedelta] = {
    ServiceTier.CRITICAL: timedelta(minutes=5),
    ServiceTier.HIGH: timedelta(minutes=15),
    ServiceTier.STANDARD: timedelta(hours=1),
}


class FailoverStatus(str, Enum):
    PRIMARY = "primary"
    DEGRADED = "degraded"
    FAILING_OVER = "failing_over"
    FAILED_OVER = "failed_over"
    RECOVERED = "recovered"


@dataclass
class HealthCheckResult:
    service: str
    healthy: bool
    response_time_ms: float
    error: Optional[str] = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ServiceState:
    service: str
    tier: ServiceTier
    region_primary: str
    region_secondary: str
    status: FailoverStatus = FailoverStatus.PRIMARY
    consecutive_failures: int = 0


@dataclass
class FailoverEvent:
    service: str
    from_region: str
    to_region: str
    triggered_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    reason: str = ""

    @property
    def duration(self) -> Optional[timedelta]:
        if self.completed_at is None:
            return None
        return self.completed_at - self.triggered_at


@dataclass
class DrillResult:
    service: str
    tier: ServiceTier
    backup_used: BackupMetadata
    achieved_rto: timedelta
    achieved_rpo: timedelta
    rto_met: bool
    rpo_met: bool

    @property
    def passed(self) -> bool:
        return self.rto_met and self.rpo_met


class HealthCheck(Protocol):
    """Pluggable health probe."""

    def check(self, service: str) -> HealthCheckResult: ...


NotificationCallback = Callable[[str, Dict[str, str]], None]


class RecoveryManager:
    """Coordinates DR for one or more services."""

    FAILURE_THRESHOLD = 3  # consecutive failures before triggering failover

    def __init__(
        self,
        backup_manager: BackupManager,
        health_check: HealthCheck,
        notify: Optional[NotificationCallback] = None,
    ):
        self.backups = backup_manager
        self.health_check = health_check
        self.notify = notify or (lambda topic, payload: None)
        self.services: Dict[str, ServiceState] = {}
        self.failover_history: List[FailoverEvent] = []

    def register_service(
        self,
        service: str,
        tier: ServiceTier,
        region_primary: str,
        region_secondary: str,
    ) -> ServiceState:
        state = ServiceState(
            service=service,
            tier=tier,
            region_primary=region_primary,
            region_secondary=region_secondary,
        )
        self.services[service] = state
        return state

    def evaluate_health(self) -> Dict[str, HealthCheckResult]:
        """Probe all registered services and update internal state."""
        results: Dict[str, HealthCheckResult] = {}
        for name, state in self.services.items():
            result = self.health_check.check(name)
            results[name] = result
            if result.healthy:
                if state.status is FailoverStatus.DEGRADED:
                    state.status = FailoverStatus.PRIMARY
                    self._emit(state, "recovered")
                state.consecutive_failures = 0
            else:
                state.consecutive_failures += 1
                if state.status is FailoverStatus.PRIMARY:
                    state.status = FailoverStatus.DEGRADED
                    self._emit(state, "degraded", error=result.error)
                if state.consecutive_failures >= self.FAILURE_THRESHOLD:
                    self._failover(state, reason=result.error or "consecutive failures")
        return results

    def restore(
        self,
        source: BackupSource,
        target_time: Optional[datetime] = None,
    ) -> bytes:
        """Point-in-time restore: pick the most recent backup not after target_time."""
        candidates = sorted(
            self.backups.list_backups(source=source),
            key=lambda m: m.created_at,
            reverse=True,
        )
        if not candidates:
            raise LookupError(f"No backups available for source {source.value}")
        if target_time is not None:
            candidates = [m for m in candidates if m.created_at <= target_time]
            if not candidates:
                raise LookupError(
                    f"No backups for source {source.value} at or before {target_time.isoformat()}"
                )
        chosen = candidates[0]
        logger.info("Restoring %s from backup %s", source.value, chosen.backup_id)
        return self.backups.restore(chosen.backup_id)

    def run_drill(
        self,
        service: str,
        source: BackupSource,
        now: Optional[datetime] = None,
    ) -> DrillResult:
        """Simulate a recovery exercise; return achieved RTO + RPO."""
        if service not in self.services:
            raise KeyError(f"Service not registered: {service}")
        state = self.services[service]
        now = now or datetime.now(timezone.utc)

        backups_for_source = sorted(
            self.backups.list_backups(source=source),
            key=lambda m: m.created_at,
            reverse=True,
        )
        if not backups_for_source:
            raise LookupError(f"No backups for source {source.value}")
        backup = backups_for_source[0]

        # Measure restore duration as the achieved RTO.
        rto_start = time.perf_counter()
        self.backups.restore(backup.backup_id)
        achieved_rto = timedelta(seconds=time.perf_counter() - rto_start)
        # RPO = gap between "now" and the backup's creation time.
        achieved_rpo = max(now - backup.created_at, timedelta(0))

        return DrillResult(
            service=service,
            tier=state.tier,
            backup_used=backup,
            achieved_rto=achieved_rto,
            achieved_rpo=achieved_rpo,
            rto_met=achieved_rto <= RTO_TARGETS[state.tier],
            rpo_met=achieved_rpo <= RPO_TARGETS[state.tier],
        )

    # -- internals -----------------------------------------------------

    def _failover(self, state: ServiceState, reason: str) -> None:
        if state.status is FailoverStatus.FAILED_OVER:
            return
        event = FailoverEvent(
            service=state.service,
            from_region=state.region_primary,
            to_region=state.region_secondary,
            triggered_at=datetime.now(timezone.utc),
            reason=reason,
        )
        state.status = FailoverStatus.FAILING_OVER
        self._emit(state, "failover_started")
        try:
            # In production this would update DNS / service mesh / Route53.
            # Here we mark the swap as successful.
            state.region_primary, state.region_secondary = state.region_secondary, state.region_primary
            state.status = FailoverStatus.FAILED_OVER
            event.success = True
        finally:
            event.completed_at = datetime.now(timezone.utc)
            self.failover_history.append(event)
            self._emit(state, "failover_completed", success=str(event.success))

    def _emit(self, state: ServiceState, kind: str, **extra: str) -> None:
        payload = {
            "service": state.service,
            "tier": state.tier.value,
            "status": state.status.value,
            "primary_region": state.region_primary,
            "secondary_region": state.region_secondary,
            **extra,
        }
        try:
            self.notify(kind, payload)
        except Exception:  # pragma: no cover - notifier should not break DR
            logger.exception("Notification callback raised")
