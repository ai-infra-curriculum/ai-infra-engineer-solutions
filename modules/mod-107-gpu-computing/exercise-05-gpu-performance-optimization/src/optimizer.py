"""
GPU Performance Optimizer

Takes a BottleneckReport and produces a ranked list of OptimizationRecommendations.
Each recommendation includes:

- The technique to apply (mixed precision, gradient checkpointing,
  pinned memory + non-blocking copies, larger DataLoader worker pool,
  bigger batch, gradient accumulation, NCCL bucket-size tuning, etc.).
- Estimated speedup multiplier.
- Side effects + applicability notes.
- A short rationale citing the BottleneckReport metric that triggered
  the suggestion.

Also provides regression detection between two BottleneckReports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .profiler import (
    BottleneckReport,
    ProfileRun,
    TraceCategory,
)


logger = logging.getLogger(__name__)


class OptimizationTechnique(str, Enum):
    MIXED_PRECISION = "mixed_precision"
    GRADIENT_CHECKPOINTING = "gradient_checkpointing"
    PINNED_MEMORY = "pinned_memory"
    INCREASE_DATA_WORKERS = "increase_data_workers"
    INCREASE_BATCH_SIZE = "increase_batch_size"
    GRADIENT_ACCUMULATION = "gradient_accumulation"
    NCCL_TUNING = "nccl_tuning"
    OVERLAP_COMPUTE_COMMS = "overlap_compute_communication"
    REDUCE_PEAK_MEMORY = "reduce_peak_memory"
    PREFETCH_PIPELINE = "prefetch_pipeline"
    OPTIMIZER_FUSED = "fused_optimizer"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class OptimizationRecommendation:
    """One actionable performance improvement."""

    technique: OptimizationTechnique
    title: str
    description: str
    estimated_speedup: float  # 1.0 = no change, 1.5 = 1.5x faster
    confidence: Confidence
    side_effects: List[str] = field(default_factory=list)
    action: str = ""

    @property
    def estimated_throughput_increase_percent(self) -> float:
        return (self.estimated_speedup - 1.0) * 100.0


@dataclass
class OptimizationPlan:
    """Ranked recommendation set."""

    report: BottleneckReport
    recommendations: List[OptimizationRecommendation]
    expected_aggregate_speedup: float


class PerformanceOptimizer:
    """Derives recommendations from a BottleneckReport."""

    # When multiple recs apply, we conservatively compose their speedups
    # geometrically rather than additively.
    def recommend(self, report: BottleneckReport) -> OptimizationPlan:
        recs: List[OptimizationRecommendation] = []
        if report.is_data_loader_bound():
            recs.extend(self._data_loader_recs(report))
        if report.is_memory_movement_bound() or report.memory_movement_percent > 8.0:
            recs.extend(self._memory_movement_recs(report))
        if report.is_compute_bound() or report.gpu_compute_percent > 60.0:
            recs.extend(self._compute_recs(report))
        if report.avg_gpu_memory_utilization_percent < 50.0:
            recs.extend(self._memory_underutilized_recs(report))
        if report.avg_gpu_memory_utilization_percent > 90.0:
            recs.extend(self._memory_pressure_recs(report))
        if report.collective_percent > 10.0:
            recs.extend(self._collective_recs(report))
        if report.idle_percent > 5.0:
            recs.extend(self._idle_recs(report))
        if (
            report.multi_gpu_scaling_efficiency_percent is not None
            and report.multi_gpu_scaling_efficiency_percent < 80.0
        ):
            recs.extend(self._scaling_recs(report))

        # Dedup by technique, keep highest-speedup.
        seen: Dict[OptimizationTechnique, OptimizationRecommendation] = {}
        for rec in recs:
            existing = seen.get(rec.technique)
            if existing is None or rec.estimated_speedup > existing.estimated_speedup:
                seen[rec.technique] = rec
        ranked = sorted(seen.values(), key=lambda r: -r.estimated_speedup)
        aggregate = 1.0
        for rec in ranked:
            aggregate *= rec.estimated_speedup
        return OptimizationPlan(
            report=report,
            recommendations=ranked,
            expected_aggregate_speedup=round(aggregate, 3),
        )

    # -- per-bottleneck rec generators ---------------------------------

    def _data_loader_recs(self, report: BottleneckReport) -> List[OptimizationRecommendation]:
        return [
            OptimizationRecommendation(
                technique=OptimizationTechnique.INCREASE_DATA_WORKERS,
                title="Increase DataLoader worker pool",
                description=(
                    f"Data loading is {report.data_loading_percent:.1f}% of step "
                    "time. Increase num_workers and persistent_workers=True so the "
                    "GPU is not waiting on the input pipeline."
                ),
                estimated_speedup=1.30,
                confidence=Confidence.HIGH,
                side_effects=["Higher host RAM usage; pin a CPU per worker"],
                action="DataLoader(num_workers=4*num_gpus, persistent_workers=True)",
            ),
            OptimizationRecommendation(
                technique=OptimizationTechnique.PREFETCH_PIPELINE,
                title="Prefetch next batch on GPU stream",
                description=(
                    "Overlap data loading with the previous step's compute by "
                    "prefetching the next batch into pinned memory and copying via "
                    "a dedicated CUDA stream."
                ),
                estimated_speedup=1.15,
                confidence=Confidence.MEDIUM,
                side_effects=["Slightly higher GPU memory baseline"],
                action="Use torch.utils.data.DataLoader(prefetch_factor=4) with pinned memory",
            ),
        ]

    def _memory_movement_recs(self, report: BottleneckReport) -> List[OptimizationRecommendation]:
        return [
            OptimizationRecommendation(
                technique=OptimizationTechnique.PINNED_MEMORY,
                title="Use pinned memory + non-blocking copies",
                description=(
                    "H2D copies are non-trivial; pinned host buffers + "
                    ".to(device, non_blocking=True) let the runtime overlap the "
                    "transfer with compute."
                ),
                estimated_speedup=1.08,
                confidence=Confidence.HIGH,
                action="pin_memory=True; tensor.to('cuda', non_blocking=True)",
            ),
        ]

    def _compute_recs(self, report: BottleneckReport) -> List[OptimizationRecommendation]:
        recs = [
            OptimizationRecommendation(
                technique=OptimizationTechnique.MIXED_PRECISION,
                title="Enable mixed-precision (AMP) training",
                description=(
                    f"Forward + backward dominate ({report.gpu_compute_percent:.1f}% "
                    "of step time). Mixed precision typically delivers 1.6-2.0x on "
                    "modern GPUs with TensorCores."
                ),
                estimated_speedup=1.7,
                confidence=Confidence.HIGH,
                side_effects=["Need a GradScaler to avoid loss-underflow"],
                action="torch.cuda.amp.autocast() + GradScaler",
            ),
            OptimizationRecommendation(
                technique=OptimizationTechnique.OPTIMIZER_FUSED,
                title="Use a fused optimizer kernel",
                description=(
                    "Optimizer step shows non-trivial overhead; a fused kernel "
                    "(e.g. apex / torch.optim.Adam(fused=True)) reduces launches."
                ),
                estimated_speedup=1.05,
                confidence=Confidence.MEDIUM,
                action="torch.optim.Adam(model.parameters(), fused=True)",
            ),
        ]
        return recs

    def _memory_underutilized_recs(self, report) -> List[OptimizationRecommendation]:
        return [
            OptimizationRecommendation(
                technique=OptimizationTechnique.INCREASE_BATCH_SIZE,
                title="Increase batch size",
                description=(
                    f"GPU memory is only {report.avg_gpu_memory_utilization_percent:.0f}% "
                    "utilised. Doubling batch size improves throughput at constant "
                    "kernel launch overhead."
                ),
                estimated_speedup=1.4,
                confidence=Confidence.HIGH,
                side_effects=["May require LR warmup + scaling"],
                action="Increase batch_size; rerun warm-up; rescale LR linearly",
            ),
        ]

    def _memory_pressure_recs(self, report) -> List[OptimizationRecommendation]:
        return [
            OptimizationRecommendation(
                technique=OptimizationTechnique.GRADIENT_CHECKPOINTING,
                title="Enable activation checkpointing",
                description=(
                    "Activation tensors dominate peak memory; checkpointing trades "
                    "~30% compute for ~50% less peak memory, allowing larger batches."
                ),
                estimated_speedup=1.1,
                confidence=Confidence.MEDIUM,
                side_effects=["Backward pass is ~20-30% slower per call"],
                action="torch.utils.checkpoint.checkpoint(...) on the largest blocks",
            ),
            OptimizationRecommendation(
                technique=OptimizationTechnique.REDUCE_PEAK_MEMORY,
                title="Offload optimizer state to CPU",
                description=(
                    "Optimizer state is a major source of memory pressure for "
                    "large models. ZeRO-style optimizer-state offload frees VRAM."
                ),
                estimated_speedup=1.05,
                confidence=Confidence.LOW,
                action="Use DeepSpeed ZeRO-1 or FSDP optimizer-state sharding",
            ),
            OptimizationRecommendation(
                technique=OptimizationTechnique.GRADIENT_ACCUMULATION,
                title="Use gradient accumulation",
                description=(
                    "If you can't fit the desired batch size, accumulate over N "
                    "micro-batches before optimizer.step() to maintain effective "
                    "batch without OOM."
                ),
                estimated_speedup=1.0,  # neutral: enables larger effective batch
                confidence=Confidence.HIGH,
                action="Run forward+backward N times, call optimizer.step() every Nth iteration",
            ),
        ]

    def _collective_recs(self, report) -> List[OptimizationRecommendation]:
        return [
            OptimizationRecommendation(
                technique=OptimizationTechnique.NCCL_TUNING,
                title="Tune NCCL bucket size",
                description=(
                    f"Collectives are {report.collective_percent:.1f}% of step time. "
                    "Bigger bucket sizes coalesce more gradients per AllReduce, "
                    "improving bandwidth utilisation."
                ),
                estimated_speedup=1.12,
                confidence=Confidence.MEDIUM,
                action="DDP(model, bucket_cap_mb=50) or higher",
            ),
            OptimizationRecommendation(
                technique=OptimizationTechnique.OVERLAP_COMPUTE_COMMS,
                title="Overlap backward + AllReduce",
                description=(
                    "Use DDP's gradient bucket hooks (or FSDP) so gradients are "
                    "all-reduced as soon as their bucket fills during backward, "
                    "overlapping with continued backward compute."
                ),
                estimated_speedup=1.18,
                confidence=Confidence.HIGH,
                action="DistributedDataParallel(model) with default bucket strategy",
            ),
        ]

    def _idle_recs(self, report) -> List[OptimizationRecommendation]:
        return [
            OptimizationRecommendation(
                technique=OptimizationTechnique.PREFETCH_PIPELINE,
                title="Reduce idle time between steps",
                description=(
                    f"GPU is idle {report.idle_percent:.1f}% of step time. Profile "
                    "with Nsight Systems to find the host-side gap and overlap with "
                    "prefetching or asynchronous logging."
                ),
                estimated_speedup=1.05,
                confidence=Confidence.LOW,
                action="Identify host-side stalls in nsys timeline view",
            ),
        ]

    def _scaling_recs(self, report) -> List[OptimizationRecommendation]:
        return [
            OptimizationRecommendation(
                technique=OptimizationTechnique.OVERLAP_COMPUTE_COMMS,
                title="Improve multi-GPU scaling efficiency",
                description=(
                    f"Scaling efficiency = "
                    f"{report.multi_gpu_scaling_efficiency_percent:.0f}%. Verify "
                    "DDP gradient-bucket overlap, NCCL_DEBUG=INFO topology, and "
                    "consider gradient compression."
                ),
                estimated_speedup=1.20,
                confidence=Confidence.MEDIUM,
                action=(
                    "Check NCCL topology with NCCL_DEBUG=INFO; consider PowerSGD"
                    " gradient compression"
                ),
            ),
        ]


# -- Regression detection -----------------------------------------------


@dataclass
class RegressionReport:
    """Compare two performance reports."""

    baseline_throughput: float
    candidate_threshold_throughput: float  # current run's throughput
    delta_percent: float
    regressed: bool
    threshold_percent: float


def detect_regression(
    baseline: BottleneckReport,
    candidate: BottleneckReport,
    *,
    threshold_percent: float = 5.0,
) -> RegressionReport:
    """Return a regression report if candidate is >threshold_percent slower."""
    baseline_tp = baseline.avg_throughput_samples_per_sec
    cand_tp = candidate.avg_throughput_samples_per_sec
    if baseline_tp <= 0:
        return RegressionReport(
            baseline_throughput=baseline_tp,
            candidate_threshold_throughput=cand_tp,
            delta_percent=0.0,
            regressed=False,
            threshold_percent=threshold_percent,
        )
    delta = (cand_tp - baseline_tp) / baseline_tp * 100.0
    regressed = delta < -threshold_percent
    return RegressionReport(
        baseline_throughput=baseline_tp,
        candidate_threshold_throughput=cand_tp,
        delta_percent=round(delta, 3),
        regressed=regressed,
        threshold_percent=threshold_percent,
    )
