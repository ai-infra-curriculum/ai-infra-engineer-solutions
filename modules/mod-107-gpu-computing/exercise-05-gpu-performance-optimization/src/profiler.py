"""
GPU Performance Profiler

Captures per-step timing breakdowns + kernel-level profiles + memory
metrics + multi-GPU communication overhead. The profiler abstracts the
underlying telemetry source (PyTorch Profiler, NVIDIA Nsight, DCGM)
behind a TraceSource Protocol so the analyzer + optimizer in
optimizer.py can work uniformly across data sources.

A synthetic SyntheticTraceSource is provided for tests + the CLI demo.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Protocol


logger = logging.getLogger(__name__)


class TraceCategory(str, Enum):
    """High-level category for a kernel/op in the trace."""

    DATA_LOADING = "data_loading"
    H2D_COPY = "h2d_copy"
    D2H_COPY = "d2h_copy"
    FORWARD = "forward"
    BACKWARD = "backward"
    OPTIMIZER = "optimizer"
    COLLECTIVE = "collective"  # AllReduce / AllGather etc
    IDLE = "idle"


@dataclass(frozen=True)
class TraceEvent:
    """One event captured from the profiler."""

    name: str
    category: TraceCategory
    start_ms: float
    duration_ms: float
    bytes_moved: int = 0  # for copies + collectives
    flops: float = 0.0  # for compute kernels
    device_id: Optional[str] = None
    stream: Optional[str] = None

    @property
    def end_ms(self) -> float:
        return self.start_ms + self.duration_ms


@dataclass
class GpuMemorySnapshot:
    """One memory observation."""

    timestamp_ms: float
    allocated_gb: float
    reserved_gb: float
    peak_gb: float
    capacity_gb: float

    @property
    def utilization_percent(self) -> float:
        if self.capacity_gb <= 0:
            return 0.0
        return self.allocated_gb / self.capacity_gb * 100.0


@dataclass
class TrainingStepProfile:
    """All events + memory + step metadata for a single training step."""

    step: int
    events: List[TraceEvent]
    memory: List[GpuMemorySnapshot]
    batch_size: int
    samples_processed: int
    step_duration_ms: float


@dataclass
class ProfileRun:
    """Aggregated profile over multiple steps."""

    name: str
    steps: List[TrainingStepProfile]
    device_count: int
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_duration_ms(self) -> float:
        return sum(s.step_duration_ms for s in self.steps)

    @property
    def total_samples(self) -> int:
        return sum(s.samples_processed for s in self.steps)


# -- Trace sources ------------------------------------------------------


class TraceSource(Protocol):
    """Pluggable trace source — PyTorch Profiler / Nsight / DCGM / synthetic."""

    def collect(self, *, steps: int, batch_size: int) -> ProfileRun: ...


@dataclass
class SyntheticTraceProfile:
    """Knobs for generating deterministic synthetic profiles."""

    # Approximate per-step phase durations in milliseconds.
    data_loading_ms: float = 50.0
    h2d_copy_ms: float = 8.0
    forward_ms: float = 90.0
    backward_ms: float = 120.0
    optimizer_ms: float = 15.0
    collective_ms: float = 0.0  # >0 for multi-GPU
    idle_ms: float = 5.0
    forward_flops: float = 4.5e11
    backward_flops: float = 9.0e11
    allocated_gb: float = 12.0
    peak_gb: float = 15.0
    capacity_gb: float = 40.0
    device_count: int = 1


class SyntheticTraceSource:
    """Generates deterministic ProfileRuns for tests + the CLI demo."""

    def __init__(self, profile: Optional[SyntheticTraceProfile] = None):
        self.profile = profile or SyntheticTraceProfile()

    def collect(self, *, steps: int = 50, batch_size: int = 32) -> ProfileRun:
        run_steps: List[TrainingStepProfile] = []
        for step in range(steps):
            events = self._step_events(step)
            step_duration = sum(e.duration_ms for e in events)
            memory = [
                GpuMemorySnapshot(
                    timestamp_ms=step * step_duration,
                    allocated_gb=self.profile.allocated_gb,
                    reserved_gb=self.profile.allocated_gb + 1.0,
                    peak_gb=self.profile.peak_gb,
                    capacity_gb=self.profile.capacity_gb,
                ),
            ]
            run_steps.append(TrainingStepProfile(
                step=step, events=events, memory=memory,
                batch_size=batch_size,
                samples_processed=batch_size,
                step_duration_ms=step_duration,
            ))
        return ProfileRun(
            name="synthetic-run",
            steps=run_steps,
            device_count=self.profile.device_count,
        )

    def _step_events(self, step: int) -> List[TraceEvent]:
        p = self.profile
        t = 0.0
        events: List[TraceEvent] = []
        events.append(TraceEvent("data_load_batch", TraceCategory.DATA_LOADING,
                                 start_ms=t, duration_ms=p.data_loading_ms))
        t += p.data_loading_ms
        events.append(TraceEvent("memcpy_h2d", TraceCategory.H2D_COPY,
                                 start_ms=t, duration_ms=p.h2d_copy_ms,
                                 bytes_moved=int(p.h2d_copy_ms * 1e6)))
        t += p.h2d_copy_ms
        events.append(TraceEvent("forward", TraceCategory.FORWARD,
                                 start_ms=t, duration_ms=p.forward_ms,
                                 flops=p.forward_flops))
        t += p.forward_ms
        events.append(TraceEvent("backward", TraceCategory.BACKWARD,
                                 start_ms=t, duration_ms=p.backward_ms,
                                 flops=p.backward_flops))
        t += p.backward_ms
        events.append(TraceEvent("optimizer.step", TraceCategory.OPTIMIZER,
                                 start_ms=t, duration_ms=p.optimizer_ms))
        t += p.optimizer_ms
        if p.collective_ms > 0:
            events.append(TraceEvent("nccl.all_reduce", TraceCategory.COLLECTIVE,
                                     start_ms=t, duration_ms=p.collective_ms,
                                     bytes_moved=int(p.collective_ms * 5e6)))
            t += p.collective_ms
        if p.idle_ms > 0:
            events.append(TraceEvent("idle", TraceCategory.IDLE,
                                     start_ms=t, duration_ms=p.idle_ms))
        return events


# -- Aggregator + bottleneck analyzer ----------------------------------


@dataclass
class CategoryBreakdown:
    category: TraceCategory
    total_ms: float
    percent: float
    count: int


@dataclass
class BottleneckReport:
    """Identifies the dominant phase + utilization metrics."""

    primary_bottleneck: TraceCategory
    breakdown: List[CategoryBreakdown]
    gpu_compute_percent: float
    data_loading_percent: float
    memory_movement_percent: float
    collective_percent: float
    idle_percent: float
    avg_throughput_samples_per_sec: float
    avg_gpu_memory_utilization_percent: float
    multi_gpu_scaling_efficiency_percent: Optional[float]

    def is_compute_bound(self) -> bool:
        return self.primary_bottleneck in {TraceCategory.FORWARD, TraceCategory.BACKWARD}

    def is_data_loader_bound(self) -> bool:
        return self.primary_bottleneck is TraceCategory.DATA_LOADING

    def is_memory_movement_bound(self) -> bool:
        return self.primary_bottleneck in {TraceCategory.H2D_COPY, TraceCategory.D2H_COPY}

    def is_collective_bound(self) -> bool:
        return self.primary_bottleneck is TraceCategory.COLLECTIVE


class BottleneckAnalyzer:
    """Aggregates a ProfileRun into a BottleneckReport."""

    def analyze(
        self,
        run: ProfileRun,
        *,
        single_device_throughput: Optional[float] = None,
    ) -> BottleneckReport:
        if not run.steps:
            raise ValueError("ProfileRun has no steps")
        # Sum durations by category.
        category_totals: Dict[TraceCategory, float] = {c: 0.0 for c in TraceCategory}
        category_counts: Dict[TraceCategory, int] = {c: 0 for c in TraceCategory}
        for step in run.steps:
            for event in step.events:
                category_totals[event.category] += event.duration_ms
                category_counts[event.category] += 1
        total = sum(category_totals.values())
        breakdown = [
            CategoryBreakdown(
                category=cat,
                total_ms=round(ms, 2),
                percent=round((ms / total * 100.0) if total else 0.0, 2),
                count=category_counts[cat],
            )
            for cat, ms in category_totals.items()
            if ms > 0
        ]
        breakdown.sort(key=lambda b: -b.percent)
        primary = breakdown[0].category if breakdown else TraceCategory.IDLE

        # Throughput.
        total_seconds = run.total_duration_ms / 1000.0
        throughput = (
            run.total_samples / total_seconds if total_seconds > 0 else 0.0
        )

        # Memory utilization (average across captured snapshots).
        mem_samples = [
            s.utilization_percent
            for step in run.steps for s in step.memory if s.capacity_gb > 0
        ]
        avg_mem = statistics.mean(mem_samples) if mem_samples else 0.0

        # Multi-GPU scaling efficiency.
        scaling = None
        if run.device_count > 1 and single_device_throughput:
            ideal = single_device_throughput * run.device_count
            scaling = round(throughput / ideal * 100.0, 2) if ideal > 0 else None

        compute_pct = (
            category_totals[TraceCategory.FORWARD]
            + category_totals[TraceCategory.BACKWARD]
            + category_totals[TraceCategory.OPTIMIZER]
        ) / total * 100.0 if total else 0.0
        loading_pct = category_totals[TraceCategory.DATA_LOADING] / total * 100.0 if total else 0.0
        mem_movement_pct = (
            category_totals[TraceCategory.H2D_COPY]
            + category_totals[TraceCategory.D2H_COPY]
        ) / total * 100.0 if total else 0.0
        collective_pct = category_totals[TraceCategory.COLLECTIVE] / total * 100.0 if total else 0.0
        idle_pct = category_totals[TraceCategory.IDLE] / total * 100.0 if total else 0.0

        return BottleneckReport(
            primary_bottleneck=primary,
            breakdown=breakdown,
            gpu_compute_percent=round(compute_pct, 2),
            data_loading_percent=round(loading_pct, 2),
            memory_movement_percent=round(mem_movement_pct, 2),
            collective_percent=round(collective_pct, 2),
            idle_percent=round(idle_pct, 2),
            avg_throughput_samples_per_sec=round(throughput, 2),
            avg_gpu_memory_utilization_percent=round(avg_mem, 2),
            multi_gpu_scaling_efficiency_percent=scaling,
        )
