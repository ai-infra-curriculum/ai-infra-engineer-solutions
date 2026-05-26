"""Tests for the GPU cluster manager + allocators + monitoring."""

from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from src.cluster_manager import (
    ClusterManager,
    GpuDevice,
    GpuType,
    Job,
    JobStatus,
    Node,
    Priority,
    TeamQuota,
)
from src.gpu_allocator import (
    AssignmentPlan,
    BinPackingScheduler,
    FIFOScheduler,
    PriorityScheduler,
    schedule_and_apply,
)
from src.monitoring import (
    CostAccountant,
    DeviceHealthState,
    GpuTelemetrySample,
    HealthMonitor,
    devices_by_type,
)


def _build_cluster() -> ClusterManager:
    manager = ClusterManager()
    manager.register_node(Node(
        node_id="node-1",
        devices=[
            GpuDevice(device_id="g0", node_id="node-1", gpu_type=GpuType.A100, memory_gb=80),
            GpuDevice(device_id="g1", node_id="node-1", gpu_type=GpuType.A100, memory_gb=80),
        ],
        cpu_cores=64, memory_gb=256,
    ))
    manager.register_node(Node(
        node_id="node-2",
        devices=[
            GpuDevice(device_id="g2", node_id="node-2", gpu_type=GpuType.V100, memory_gb=32),
            GpuDevice(device_id="g3", node_id="node-2", gpu_type=GpuType.T4, memory_gb=16),
        ],
        cpu_cores=32, memory_gb=128,
    ))
    manager.set_team_quota("alpha", max_gpu_fractions=3.0)
    manager.set_team_quota("beta", max_gpu_fractions=1.0)
    return manager


class TestClusterManager:
    def test_register_node_unique(self):
        manager = _build_cluster()
        with pytest.raises(ValueError):
            manager.register_node(Node(
                node_id="node-1", devices=[], cpu_cores=1, memory_gb=1,
            ))

    def test_submit_validates_fraction(self):
        manager = _build_cluster()
        with pytest.raises(ValueError):
            manager.submit_job(team="alpha", name="bad", requested_fraction=1.5)
        with pytest.raises(ValueError):
            manager.submit_job(team="alpha", name="zero", requested_fraction=0.0)

    def test_submit_validates_gpu_count(self):
        manager = _build_cluster()
        with pytest.raises(ValueError):
            manager.submit_job(team="alpha", name="bad", requested_gpu_count=0)

    def test_assign_marks_running(self):
        manager = _build_cluster()
        job = manager.submit_job(team="alpha", name="t1", requested_fraction=1.0,
                                  requested_gpu_count=1, preferred_gpu_type=GpuType.A100)
        manager.assign_job(job.job_id, ["g0"])
        assert job.status is JobStatus.RUNNING
        assert manager.team_quotas["alpha"].used_gpu_fractions == 1.0
        assert manager._find_device("g0").allocated_fraction == 1.0

    def test_complete_releases_resources(self):
        manager = _build_cluster()
        job = manager.submit_job(team="alpha", name="t1", requested_fraction=1.0)
        manager.assign_job(job.job_id, ["g0"])
        manager.complete_job(job.job_id)
        assert job.status is JobStatus.COMPLETED
        assert manager.team_quotas["alpha"].used_gpu_fractions == 0.0
        assert manager._find_device("g0").allocated_fraction == 0.0

    def test_assign_rejects_over_quota(self):
        manager = _build_cluster()
        job = manager.submit_job(team="beta", name="t1", requested_fraction=1.0,
                                  requested_gpu_count=2)
        with pytest.raises(RuntimeError, match="quota"):
            manager.assign_job(job.job_id, ["g0", "g1"])

    def test_assign_rejects_overcommit(self):
        manager = _build_cluster()
        job_a = manager.submit_job(team="alpha", name="a", requested_fraction=0.7)
        job_b = manager.submit_job(team="alpha", name="b", requested_fraction=0.5)
        manager.assign_job(job_a.job_id, ["g0"])
        with pytest.raises(RuntimeError):
            manager.assign_job(job_b.job_id, ["g0"])

    def test_preempt_returns_job_to_pending(self):
        manager = _build_cluster()
        job = manager.submit_job(team="alpha", name="t1", requested_fraction=1.0)
        manager.assign_job(job.job_id, ["g0"])
        manager.preempt_job(job.job_id)
        assert job.status is JobStatus.PENDING
        assert manager._find_device("g0").allocated_fraction == 0.0

    def test_preempt_rejects_non_preemptible(self):
        manager = _build_cluster()
        job = manager.submit_job(team="alpha", name="t1", requested_fraction=1.0,
                                  preemptible=False)
        manager.assign_job(job.job_id, ["g0"])
        with pytest.raises(RuntimeError):
            manager.preempt_job(job.job_id)

    def test_unhealthy_device_fails_running_jobs(self):
        manager = _build_cluster()
        job = manager.submit_job(team="alpha", name="t1", requested_fraction=1.0)
        manager.assign_job(job.job_id, ["g0"])
        manager.mark_device_unhealthy("g0", reason="ECC")
        assert job.status is JobStatus.FAILED
        assert manager._find_device("g0").allocated_fraction == 0.0

    def test_cluster_utilization(self):
        manager = _build_cluster()
        job_a = manager.submit_job(team="alpha", name="a", requested_fraction=1.0)
        manager.assign_job(job_a.job_id, ["g0"])
        # 1 of 4 GPUs fully allocated → 25%.
        assert manager.cluster_utilization() == 0.25


class TestSchedulers:
    def test_fifo_orders_by_submission(self):
        manager = _build_cluster()
        job_a = manager.submit_job(team="alpha", name="a", requested_fraction=1.0,
                                    preferred_gpu_type=GpuType.A100)
        job_b = manager.submit_job(team="alpha", name="b", requested_fraction=1.0,
                                    preferred_gpu_type=GpuType.A100)
        plan = schedule_and_apply(manager, FIFOScheduler())
        assert plan.assignments[0].job_id == job_a.job_id
        assert plan.assignments[1].job_id == job_b.job_id

    def test_priority_jumps_queue(self):
        manager = _build_cluster()
        low = manager.submit_job(team="alpha", name="low", requested_fraction=1.0,
                                  preferred_gpu_type=GpuType.A100,
                                  priority=Priority.LOW)
        high = manager.submit_job(team="alpha", name="high", requested_fraction=1.0,
                                   preferred_gpu_type=GpuType.A100,
                                   priority=Priority.CRITICAL)
        plan = schedule_and_apply(manager, PriorityScheduler())
        # Priority scheduler runs the critical job first.
        assert plan.assignments[0].job_id == high.job_id

    def test_priority_preempts_lower(self):
        manager = _build_cluster()
        # Use up both A100 devices with a low-priority job from beta
        # (quota allows only 1 GPU for beta — so submit two beta jobs
        # of 1.0 fraction each is too much; use alpha which has 3.0).
        low_a = manager.submit_job(team="alpha", name="low-a",
                                    requested_fraction=1.0,
                                    preferred_gpu_type=GpuType.A100,
                                    priority=Priority.LOW)
        low_b = manager.submit_job(team="alpha", name="low-b",
                                    requested_fraction=1.0,
                                    preferred_gpu_type=GpuType.A100,
                                    priority=Priority.LOW)
        schedule_and_apply(manager, PriorityScheduler())
        # Both A100 GPUs should be running low-priority jobs.
        assert manager._find_device("g0").allocated_fraction == 1.0
        assert manager._find_device("g1").allocated_fraction == 1.0
        # Submit a critical job that needs an A100.
        critical = manager.submit_job(team="alpha", name="critical",
                                       requested_fraction=1.0,
                                       preferred_gpu_type=GpuType.A100,
                                       priority=Priority.CRITICAL)
        plan = schedule_and_apply(manager, PriorityScheduler())
        assert critical.status is JobStatus.RUNNING
        assert plan.preemptions  # at least one low-priority job was preempted
        # The preempted job is back in PENDING.
        preempted = [manager.jobs[j_id] for j_id in plan.preemptions]
        assert all(p.status is JobStatus.PENDING for p in preempted)

    def test_priority_skips_non_preemptible(self):
        manager = _build_cluster()
        non_preempt_a = manager.submit_job(team="alpha", name="np-a",
                                            requested_fraction=1.0,
                                            preferred_gpu_type=GpuType.A100,
                                            priority=Priority.LOW,
                                            preemptible=False)
        non_preempt_b = manager.submit_job(team="alpha", name="np-b",
                                            requested_fraction=1.0,
                                            preferred_gpu_type=GpuType.A100,
                                            priority=Priority.LOW,
                                            preemptible=False)
        schedule_and_apply(manager, PriorityScheduler())
        critical = manager.submit_job(team="alpha", name="critical",
                                       requested_fraction=1.0,
                                       preferred_gpu_type=GpuType.A100,
                                       priority=Priority.CRITICAL)
        plan = schedule_and_apply(manager, PriorityScheduler())
        # The critical job can't be placed; rejection recorded.
        assert critical.status is JobStatus.PENDING
        assert any(r["job_id"] == critical.job_id for r in plan.rejections)

    def test_bin_packing_prefers_tight_fit(self):
        manager = ClusterManager()
        manager.register_node(Node(
            node_id="n", devices=[
                GpuDevice(device_id="big", node_id="n",
                          gpu_type=GpuType.A100, memory_gb=80),
                GpuDevice(device_id="small", node_id="n",
                          gpu_type=GpuType.A100, memory_gb=80,
                          allocated_fraction=0.5),  # 0.5 free
            ],
            cpu_cores=8, memory_gb=64,
        ))
        # 0.5-fraction request should land on the "small" device
        # (best-fit) rather than the "big" empty one.
        job = manager.submit_job(team="t", name="x", requested_fraction=0.5)
        plan = schedule_and_apply(manager, BinPackingScheduler())
        assert plan.assignments[0].device_ids == ["small"]


class TestHealthMonitor:
    def _sample(self, *, temp=60.0, ecc=0, util=80.0, device_id="g0") -> GpuTelemetrySample:
        return GpuTelemetrySample(
            device_id=device_id,
            timestamp=datetime.now(timezone.utc),
            utilization_percent=util,
            memory_used_gb=10.0,
            temperature_c=temp,
            ecc_errors=ecc,
            power_draw_w=200.0,
        )

    def test_healthy_sample_yields_no_event(self):
        monitor = HealthMonitor()
        result = monitor.ingest(self._sample())
        assert result is None

    def test_high_temperature_critical(self):
        monitor = HealthMonitor()
        result = monitor.ingest(self._sample(temp=96.0))
        assert result is not None
        assert result.state is DeviceHealthState.UNHEALTHY

    def test_warm_temperature_degraded(self):
        monitor = HealthMonitor()
        result = monitor.ingest(self._sample(temp=88.0))
        assert result is not None
        assert result.state is DeviceHealthState.DEGRADED

    def test_ecc_unhealthy(self):
        monitor = HealthMonitor()
        result = monitor.ingest(self._sample(ecc=10))
        assert result is not None
        assert result.state is DeviceHealthState.UNHEALTHY

    def test_stuck_idle_detection(self):
        monitor = HealthMonitor()
        for _ in range(HealthMonitor.IDLE_WINDOW_SAMPLES):
            monitor.ingest(self._sample(util=1.0))
        events = monitor.stuck_idle_devices(allocated_device_ids=["g0"])
        assert events
        assert events[0].state is DeviceHealthState.DEGRADED


class TestCostAccountant:
    def test_records_completed_job(self):
        manager = _build_cluster()
        job = manager.submit_job(team="alpha", name="t", requested_fraction=1.0,
                                  preferred_gpu_type=GpuType.A100)
        manager.assign_job(job.job_id, ["g0"])
        # Force 2 hours of runtime.
        assert job.started_at is not None
        job.ended_at = job.started_at + timedelta(hours=2)
        accountant = CostAccountant()
        counts = devices_by_type(manager, job.assigned_devices)
        accountant.record_completed(job, devices_by_type=counts)
        report = accountant.report()
        assert len(report) == 1
        # 2h × $3.673/h = $7.35 (within rounding).
        assert report[0].total_cost_usd == pytest.approx(7.35, abs=0.01)

    def test_devices_by_type_groups_correctly(self):
        manager = _build_cluster()
        counts = devices_by_type(manager, ["g0", "g1", "g2", "g3"])
        assert counts[GpuType.A100] == 2
        assert counts[GpuType.V100] == 1
        assert counts[GpuType.T4] == 1
