"""
GPU Cluster Monitoring

Two layers of monitoring:

- HealthMonitor: ingests per-device telemetry samples and detects
  device failures (high temp, ECC errors, sustained zero utilization
  while allocated). Returns DeviceHealthEvent records the cluster
  manager uses to evict jobs.
- CostAccountant: rolls per-team GPU-hour usage into a chargeback
  report priced by GPU type.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Deque, Dict, Iterable, List, Optional

from .cluster_manager import ClusterManager, GpuType, Job, JobStatus


logger = logging.getLogger(__name__)


# Approximate hourly cost ($/hour) per GPU type — used for chargeback.
GPU_HOURLY_COST: Dict[GpuType, float] = {
    GpuType.T4: 0.526,
    GpuType.V100: 3.06,
    GpuType.A100: 3.673,
    GpuType.H100: 8.50,
}


class DeviceHealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class GpuTelemetrySample:
    """One DCGM-style sample for a GPU."""

    device_id: str
    timestamp: datetime
    utilization_percent: float  # 0 .. 100
    memory_used_gb: float
    temperature_c: float
    ecc_errors: int
    power_draw_w: float


@dataclass
class DeviceHealthEvent:
    """Event the cluster reacts to."""

    device_id: str
    state: DeviceHealthState
    reason: str
    detected_at: datetime


class HealthMonitor:
    """Detects failing GPUs from a stream of telemetry samples."""

    TEMP_DEGRADED_C = 85.0
    TEMP_UNHEALTHY_C = 95.0
    ECC_UNHEALTHY = 5
    IDLE_THRESHOLD_PERCENT = 5.0
    IDLE_WINDOW_SAMPLES = 5

    def __init__(self) -> None:
        self._recent: Dict[str, Deque[GpuTelemetrySample]] = defaultdict(
            lambda: deque(maxlen=self.IDLE_WINDOW_SAMPLES)
        )
        self.events: List[DeviceHealthEvent] = []

    def ingest(self, sample: GpuTelemetrySample) -> Optional[DeviceHealthEvent]:
        history = self._recent[sample.device_id]
        history.append(sample)
        # Temperature checks.
        if sample.temperature_c >= self.TEMP_UNHEALTHY_C:
            return self._emit(
                sample.device_id, DeviceHealthState.UNHEALTHY,
                f"Temperature {sample.temperature_c:.1f}C exceeds critical threshold "
                f"{self.TEMP_UNHEALTHY_C}C",
                sample.timestamp,
            )
        if sample.temperature_c >= self.TEMP_DEGRADED_C:
            return self._emit(
                sample.device_id, DeviceHealthState.DEGRADED,
                f"Temperature {sample.temperature_c:.1f}C above warning threshold "
                f"{self.TEMP_DEGRADED_C}C",
                sample.timestamp,
            )
        # ECC error count.
        if sample.ecc_errors >= self.ECC_UNHEALTHY:
            return self._emit(
                sample.device_id, DeviceHealthState.UNHEALTHY,
                f"ECC error count {sample.ecc_errors} exceeds threshold "
                f"{self.ECC_UNHEALTHY}",
                sample.timestamp,
            )
        return None

    def stuck_idle_devices(self, *, allocated_device_ids: Iterable[str]) -> List[DeviceHealthEvent]:
        """Return devices that are allocated but have not produced load."""
        results: List[DeviceHealthEvent] = []
        for device_id in allocated_device_ids:
            history = self._recent.get(device_id)
            if history is None or len(history) < self.IDLE_WINDOW_SAMPLES:
                continue
            if all(s.utilization_percent < self.IDLE_THRESHOLD_PERCENT for s in history):
                last_ts = history[-1].timestamp
                evt = DeviceHealthEvent(
                    device_id=device_id,
                    state=DeviceHealthState.DEGRADED,
                    reason=(
                        f"Allocated device has been idle "
                        f"(<{self.IDLE_THRESHOLD_PERCENT}%) for "
                        f"{self.IDLE_WINDOW_SAMPLES} consecutive samples"
                    ),
                    detected_at=last_ts,
                )
                results.append(evt)
                self.events.append(evt)
        return results

    def _emit(
        self,
        device_id: str,
        state: DeviceHealthState,
        reason: str,
        ts: datetime,
    ) -> DeviceHealthEvent:
        evt = DeviceHealthEvent(
            device_id=device_id, state=state,
            reason=reason, detected_at=ts,
        )
        self.events.append(evt)
        return evt


# -- Cost accounting ----------------------------------------------------


@dataclass
class TeamCostEntry:
    """Chargeback line for one team."""

    team: str
    gpu_hours_by_type: Dict[GpuType, float]
    total_cost_usd: float


class CostAccountant:
    """Tracks team-level GPU-hours and converts them to dollars."""

    def __init__(self, *, hourly_cost: Optional[Dict[GpuType, float]] = None):
        self.hourly_cost = dict(hourly_cost or GPU_HOURLY_COST)
        self._usage: Dict[str, Dict[GpuType, float]] = defaultdict(
            lambda: {t: 0.0 for t in GpuType}
        )

    def record_completed(self, job: Job, *, devices_by_type: Dict[GpuType, int]) -> None:
        """Add GPU-hours for a finished job, indexed by GPU type used."""
        if job.started_at is None or job.ended_at is None:
            return
        elapsed_hours = (job.ended_at - job.started_at).total_seconds() / 3600.0
        for gpu_type, count in devices_by_type.items():
            gpu_hours = elapsed_hours * count * job.requested_fraction
            self._usage[job.team][gpu_type] += gpu_hours

    def report(self) -> List[TeamCostEntry]:
        entries: List[TeamCostEntry] = []
        for team, by_type in self._usage.items():
            total = sum(
                hours * self.hourly_cost.get(t, 0.0)
                for t, hours in by_type.items()
            )
            entries.append(TeamCostEntry(
                team=team,
                gpu_hours_by_type=dict(by_type),
                total_cost_usd=round(total, 2),
            ))
        return sorted(entries, key=lambda e: -e.total_cost_usd)

    def team_total(self, team: str) -> float:
        by_type = self._usage.get(team, {})
        return round(sum(
            hours * self.hourly_cost.get(t, 0.0) for t, hours in by_type.items()
        ), 2)


def devices_by_type(manager: ClusterManager, device_ids: Iterable[str]) -> Dict[GpuType, int]:
    """Group a device-id list by GPU type, for cost recording."""
    counts: Dict[GpuType, int] = defaultdict(int)
    for device_id in device_ids:
        for node in manager.nodes.values():
            for device in node.devices:
                if device.device_id == device_id:
                    counts[device.gpu_type] += 1
                    break
    return dict(counts)
