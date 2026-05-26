"""
GPU Allocator + Scheduler

Decides which pending jobs to assign to which GPUs. Three scheduler
strategies ship out of the box:

- FIFO: jobs run in submission order.
- PriorityScheduler: higher-priority jobs jump the queue; will
  preempt a running lower-priority job if no idle capacity exists.
- BinPackingScheduler: minimises fragmentation by preferring devices
  whose free_fraction matches the request most tightly.

All schedulers honor team quotas and GPU-type preferences and produce a
SchedulingPlan that the cluster manager applies atomically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .cluster_manager import (
    ClusterManager,
    ClusterSnapshot,
    GpuDevice,
    GpuType,
    Job,
    JobStatus,
    Priority,
    TeamQuota,
)


logger = logging.getLogger(__name__)


@dataclass
class AssignmentPlan:
    """One job → device list assignment."""

    job_id: str
    device_ids: List[str]
    reason: str = ""


@dataclass
class SchedulingPlan:
    """Output of a scheduler tick."""

    assignments: List[AssignmentPlan] = field(default_factory=list)
    preemptions: List[str] = field(default_factory=list)  # job_ids to preempt
    rejections: List[Dict[str, str]] = field(default_factory=list)
    # Each rejection: {"job_id": ..., "reason": ...}


# -- helpers shared by all schedulers ----------------------------------


def _eligible_devices(
    snapshot: ClusterSnapshot,
    job: Job,
) -> List[GpuDevice]:
    """Return devices that match GPU-type preference. Capacity is filtered
    against the working free_map in `_try_place` so in-flight preemptions
    are visible in the same scheduling tick."""
    devices: List[GpuDevice] = []
    for node in snapshot.nodes:
        for device in node.devices:
            if not device.healthy:
                continue
            if job.preferred_gpu_type is not None and device.gpu_type is not job.preferred_gpu_type:
                continue
            devices.append(device)
    return devices


def _quota_allows(quota: Optional[TeamQuota], total_fraction: float) -> bool:
    if quota is None:
        return True
    return total_fraction <= quota.remaining + 1e-9


def _sort_pending(jobs: List[Job]) -> List[Job]:
    """Default ordering: higher priority first, then earlier submitted_at."""
    return sorted(jobs, key=lambda j: (-int(j.priority), j.submitted_at))


# -- schedulers --------------------------------------------------------


class FIFOScheduler:
    """Schedule pending jobs in strict submission order."""

    name = "fifo"

    def plan(self, snapshot: ClusterSnapshot) -> SchedulingPlan:
        plan = SchedulingPlan()
        # Working copies of free fractions per device + quotas.
        free_map = _build_free_map(snapshot)
        used_per_team = _build_used_map(snapshot)
        for job in sorted(snapshot.pending_jobs, key=lambda j: j.submitted_at):
            decision = _try_place(job, snapshot, free_map, used_per_team)
            if decision is None:
                plan.rejections.append({
                    "job_id": job.job_id,
                    "reason": "no eligible devices or quota exhausted",
                })
                continue
            plan.assignments.append(decision)
        return plan


class PriorityScheduler:
    """Honor priority. Preempt lower-priority running jobs when needed."""

    name = "priority"

    def plan(self, snapshot: ClusterSnapshot) -> SchedulingPlan:
        plan = SchedulingPlan()
        free_map = _build_free_map(snapshot)
        used_per_team = _build_used_map(snapshot)
        running_by_priority = sorted(
            snapshot.running_jobs, key=lambda j: int(j.priority)
        )

        for job in _sort_pending(snapshot.pending_jobs):
            decision = _try_place(job, snapshot, free_map, used_per_team)
            if decision is not None:
                plan.assignments.append(decision)
                continue
            # Try preempting lower-priority running jobs that hold
            # enough GPU capacity. Greedy: walk the lowest-priority
            # running jobs and free their resources until we can fit.
            needed = job.requested_fraction * job.requested_gpu_count
            freed = 0.0
            preempt_candidates: List[Job] = []
            for running in list(running_by_priority):
                if int(running.priority) >= int(job.priority):
                    break  # no further preemption is justified
                if not running.preemptible:
                    continue
                running_total = running.requested_fraction * len(running.assigned_devices)
                preempt_candidates.append(running)
                freed += running_total
                if freed + 1e-9 >= needed:
                    break
            if freed + 1e-9 < needed:
                plan.rejections.append({
                    "job_id": job.job_id,
                    "reason": "insufficient capacity, no preemptible lower-priority jobs",
                })
                continue
            # Mark candidates for preemption and free their devices
            # in the working free_map so this scheduler tick can place
            # the high-priority job in the same plan.
            for victim in preempt_candidates:
                plan.preemptions.append(victim.job_id)
                running_by_priority.remove(victim)
                for device_id in victim.assigned_devices:
                    free_map[device_id] = min(1.0, free_map[device_id] + victim.requested_fraction)
                used_per_team[victim.team] = max(0.0, used_per_team[victim.team]
                                                  - victim.requested_fraction * len(victim.assigned_devices))
            # Retry placement with newly freed capacity.
            decision = _try_place(job, snapshot, free_map, used_per_team)
            if decision is None:
                plan.rejections.append({
                    "job_id": job.job_id,
                    "reason": "preemption freed insufficient capacity",
                })
                continue
            decision.reason = (
                f"placed after preempting {[v.job_id for v in preempt_candidates]}"
            )
            plan.assignments.append(decision)
        return plan


class BinPackingScheduler:
    """Best-fit packing: pick the device whose free fraction best matches."""

    name = "bin_packing"

    def plan(self, snapshot: ClusterSnapshot) -> SchedulingPlan:
        plan = SchedulingPlan()
        free_map = _build_free_map(snapshot)
        used_per_team = _build_used_map(snapshot)
        for job in _sort_pending(snapshot.pending_jobs):
            decision = _try_place(
                job, snapshot, free_map, used_per_team, strategy="best_fit",
            )
            if decision is None:
                plan.rejections.append({
                    "job_id": job.job_id,
                    "reason": "no eligible bin found",
                })
                continue
            plan.assignments.append(decision)
        return plan


# -- placement -----------------------------------------------------------


def _try_place(
    job: Job,
    snapshot: ClusterSnapshot,
    free_map: Dict[str, float],
    used_per_team: Dict[str, float],
    *,
    strategy: str = "first_fit",
) -> Optional[AssignmentPlan]:
    """Try to place a job; mutate free_map + used_per_team on success."""
    candidates = _eligible_devices(snapshot, job)
    candidates = [c for c in candidates if free_map[c.device_id] + 1e-9 >= job.requested_fraction]
    if len(candidates) < job.requested_gpu_count:
        return None

    if strategy == "best_fit":
        # Prefer devices with free_fraction closest to (but >=) the request.
        candidates.sort(
            key=lambda d: (
                free_map[d.device_id] - job.requested_fraction,
                d.gpu_type.value,
                d.device_id,
            ),
        )
    else:  # first_fit
        candidates.sort(key=lambda d: (d.node_id, d.device_id))

    chosen = candidates[: job.requested_gpu_count]
    total_fraction = job.requested_fraction * job.requested_gpu_count
    quota = snapshot.team_quotas.get(job.team)
    if quota is not None:
        already = used_per_team.get(job.team, 0.0)
        if already + total_fraction > quota.max_gpu_fractions + 1e-9:
            return None
    for device in chosen:
        free_map[device.device_id] -= job.requested_fraction
    used_per_team[job.team] = used_per_team.get(job.team, 0.0) + total_fraction
    return AssignmentPlan(
        job_id=job.job_id,
        device_ids=[d.device_id for d in chosen],
        reason=f"placed via {strategy}",
    )


def _build_free_map(snapshot: ClusterSnapshot) -> Dict[str, float]:
    free: Dict[str, float] = {}
    for node in snapshot.nodes:
        for device in node.devices:
            free[device.device_id] = device.free_fraction if device.healthy else 0.0
    return free


def _build_used_map(snapshot: ClusterSnapshot) -> Dict[str, float]:
    used: Dict[str, float] = {}
    for team_name, quota in snapshot.team_quotas.items():
        used[team_name] = quota.used_gpu_fractions
    return used


# -- driver ------------------------------------------------------------


def schedule_and_apply(
    manager: ClusterManager,
    scheduler,
) -> SchedulingPlan:
    """Compute a scheduling plan against the current cluster + apply it."""
    snapshot = manager.snapshot()
    plan = scheduler.plan(snapshot)
    for job_id in plan.preemptions:
        manager.preempt_job(job_id)
    for assignment in plan.assignments:
        manager.assign_job(assignment.job_id, assignment.device_ids)
    return plan
