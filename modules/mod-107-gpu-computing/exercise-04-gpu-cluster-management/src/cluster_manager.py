"""
GPU Cluster Manager

Tracks the cluster's GPU inventory, per-team quotas, and the lifecycle
of submitted Jobs. The scheduler in gpu_allocator.py consumes
ClusterState snapshots produced here; this module is the source of
truth for cluster state and concurrency.

The data model:

- GpuDevice: one physical GPU with type, memory, and current
  fractional allocation [0.0, 1.0].
- Node: a host with N GpuDevices and a node-level allocatable CPU/MEM.
- Job: a request to run with N GPU fractions, GPU-type preference,
  priority, and team attribution.
- TeamQuota: per-team caps on concurrent GPU usage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional


logger = logging.getLogger(__name__)


class GpuType(str, Enum):
    T4 = "T4"
    V100 = "V100"
    A100 = "A100"
    H100 = "H100"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PREEMPTED = "preempted"
    CANCELLED = "cancelled"


class Priority(int, Enum):
    LOW = 0
    NORMAL = 10
    HIGH = 50
    CRITICAL = 100


@dataclass
class GpuDevice:
    """One physical GPU."""

    device_id: str
    node_id: str
    gpu_type: GpuType
    memory_gb: int
    allocated_fraction: float = 0.0  # 0.0 .. 1.0
    healthy: bool = True
    current_job_ids: List[str] = field(default_factory=list)

    @property
    def free_fraction(self) -> float:
        return max(0.0, 1.0 - self.allocated_fraction)

    def can_fit(self, required_fraction: float) -> bool:
        return self.healthy and self.free_fraction + 1e-9 >= required_fraction


@dataclass
class Node:
    """A host with N GpuDevices."""

    node_id: str
    devices: List[GpuDevice]
    cpu_cores: int
    memory_gb: int

    def gpus_of_type(self, gpu_type: Optional[GpuType] = None) -> List[GpuDevice]:
        if gpu_type is None:
            return list(self.devices)
        return [d for d in self.devices if d.gpu_type is gpu_type]


@dataclass
class TeamQuota:
    """Per-team caps."""

    team: str
    max_gpu_fractions: float  # e.g., 4.0 = up to 4 whole GPUs concurrently
    used_gpu_fractions: float = 0.0

    @property
    def remaining(self) -> float:
        return max(0.0, self.max_gpu_fractions - self.used_gpu_fractions)


@dataclass
class Job:
    """One workload request."""

    job_id: str
    team: str
    name: str
    requested_fraction: float  # how much of a single GPU is requested (1.0 = whole)
    requested_gpu_count: int = 1  # how many GPUs are needed
    preferred_gpu_type: Optional[GpuType] = None
    priority: Priority = Priority.NORMAL
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: JobStatus = JobStatus.PENDING
    assigned_devices: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    preemptible: bool = True


@dataclass
class ClusterSnapshot:
    """Read-only state passed to the scheduler."""

    nodes: List[Node]
    pending_jobs: List[Job]
    running_jobs: List[Job]
    team_quotas: Dict[str, TeamQuota]


class ClusterManager:
    """Cluster-wide registry of nodes + jobs + team quotas."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.nodes: Dict[str, Node] = {}
        self.jobs: Dict[str, Job] = {}
        self.team_quotas: Dict[str, TeamQuota] = {}
        self._next_job_id = 0
        self._clock = clock

    # -- registration --------------------------------------------------

    def register_node(self, node: Node) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"Node {node.node_id} already registered")
        self.nodes[node.node_id] = node

    def set_team_quota(self, team: str, max_gpu_fractions: float) -> TeamQuota:
        quota = TeamQuota(team=team, max_gpu_fractions=max_gpu_fractions)
        self.team_quotas[team] = quota
        return quota

    def mark_device_unhealthy(self, device_id: str, *, reason: str = "") -> None:
        device = self._find_device(device_id)
        device.healthy = False
        # Mark any running jobs on the device as failed.
        for job_id in list(device.current_job_ids):
            job = self.jobs[job_id]
            job.status = JobStatus.FAILED
            job.ended_at = self._clock()
            self._release_device(device, job_id, fraction=job.requested_fraction)

    # -- job lifecycle -------------------------------------------------

    def submit_job(
        self,
        *,
        team: str,
        name: str,
        requested_fraction: float = 1.0,
        requested_gpu_count: int = 1,
        preferred_gpu_type: Optional[GpuType] = None,
        priority: Priority = Priority.NORMAL,
        preemptible: bool = True,
    ) -> Job:
        if not 0.0 < requested_fraction <= 1.0:
            raise ValueError(f"requested_fraction must be in (0, 1], got {requested_fraction}")
        if requested_gpu_count < 1:
            raise ValueError("requested_gpu_count must be >= 1")
        self._next_job_id += 1
        job_id = f"job-{self._next_job_id:06d}"
        job = Job(
            job_id=job_id,
            team=team,
            name=name,
            requested_fraction=requested_fraction,
            requested_gpu_count=requested_gpu_count,
            preferred_gpu_type=preferred_gpu_type,
            priority=priority,
            preemptible=preemptible,
            submitted_at=self._clock(),
        )
        self.jobs[job_id] = job
        return job

    def assign_job(self, job_id: str, device_ids: List[str]) -> None:
        """Mark a job as running on the listed devices."""
        job = self.jobs[job_id]
        if job.status is not JobStatus.PENDING:
            raise RuntimeError(f"Job {job_id} is not pending (status={job.status.value})")
        quota = self._ensure_quota(job.team)
        total_fraction = job.requested_fraction * len(device_ids)
        if total_fraction > quota.remaining + 1e-9:
            raise RuntimeError(
                f"Team {job.team!r} would exceed quota "
                f"({quota.used_gpu_fractions + total_fraction:.2f} > "
                f"{quota.max_gpu_fractions:.2f})"
            )
        for device_id in device_ids:
            device = self._find_device(device_id)
            if not device.can_fit(job.requested_fraction):
                raise RuntimeError(
                    f"Device {device_id} cannot fit job {job_id} "
                    f"(free={device.free_fraction:.2f}, requested={job.requested_fraction:.2f})"
                )
        # All preconditions pass — mutate state.
        for device_id in device_ids:
            device = self._find_device(device_id)
            device.allocated_fraction += job.requested_fraction
            device.current_job_ids.append(job_id)
        job.status = JobStatus.RUNNING
        job.assigned_devices = list(device_ids)
        job.started_at = self._clock()
        quota.used_gpu_fractions += total_fraction

    def complete_job(self, job_id: str, *, status: JobStatus = JobStatus.COMPLETED) -> None:
        job = self.jobs[job_id]
        if job.status is not JobStatus.RUNNING:
            raise RuntimeError(f"Job {job_id} is not running (status={job.status.value})")
        quota = self.team_quotas[job.team]
        for device_id in job.assigned_devices:
            device = self._find_device(device_id)
            self._release_device(device, job_id, fraction=job.requested_fraction)
        total_freed = job.requested_fraction * len(job.assigned_devices)
        quota.used_gpu_fractions = max(0.0, quota.used_gpu_fractions - total_freed)
        job.status = status
        job.ended_at = self._clock()

    def preempt_job(self, job_id: str) -> None:
        """Stop a running job and return it to the pending queue."""
        job = self.jobs[job_id]
        if job.status is not JobStatus.RUNNING:
            raise RuntimeError(f"Cannot preempt non-running job {job_id}")
        if not job.preemptible:
            raise RuntimeError(f"Job {job_id} is not preemptible")
        # Free resources but keep the job record for re-scheduling.
        quota = self.team_quotas[job.team]
        for device_id in job.assigned_devices:
            device = self._find_device(device_id)
            self._release_device(device, job_id, fraction=job.requested_fraction)
        total_freed = job.requested_fraction * len(job.assigned_devices)
        quota.used_gpu_fractions = max(0.0, quota.used_gpu_fractions - total_freed)
        job.status = JobStatus.PENDING
        job.assigned_devices = []
        job.started_at = None

    # -- snapshots -----------------------------------------------------

    def snapshot(self) -> ClusterSnapshot:
        return ClusterSnapshot(
            nodes=list(self.nodes.values()),
            pending_jobs=[j for j in self.jobs.values() if j.status is JobStatus.PENDING],
            running_jobs=[j for j in self.jobs.values() if j.status is JobStatus.RUNNING],
            team_quotas=dict(self.team_quotas),
        )

    def cluster_utilization(self) -> float:
        """Total allocated GPU fraction / total available GPU fraction."""
        total_devices = sum(len(n.devices) for n in self.nodes.values())
        if total_devices == 0:
            return 0.0
        allocated = sum(
            d.allocated_fraction
            for n in self.nodes.values()
            for d in n.devices
        )
        return allocated / total_devices

    def healthy_device_count(self) -> int:
        return sum(
            1 for n in self.nodes.values() for d in n.devices if d.healthy
        )

    # -- internals -----------------------------------------------------

    def _find_device(self, device_id: str) -> GpuDevice:
        for node in self.nodes.values():
            for device in node.devices:
                if device.device_id == device_id:
                    return device
        raise KeyError(f"Unknown device {device_id}")

    def _release_device(self, device: GpuDevice, job_id: str, *, fraction: float) -> None:
        device.allocated_fraction = max(0.0, device.allocated_fraction - fraction)
        if job_id in device.current_job_ids:
            device.current_job_ids.remove(job_id)

    def _ensure_quota(self, team: str) -> TeamQuota:
        if team not in self.team_quotas:
            # Default unbounded quota when not explicitly set.
            self.team_quotas[team] = TeamQuota(team=team, max_gpu_fractions=float("inf"))
        return self.team_quotas[team]
