"""
Distributed-training strategy models

Captures the tradeoffs across DDP / TP / PP / ZeRO so a planner can
recommend a configuration for a given (model_size, gpu_memory,
cluster_size) and estimate memory + throughput.

The math is intentionally simplified (it ignores activation memory
variance with batch size + sequence length, optimizer-specific costs,
mixed-precision savings beyond a flat scale factor) so the curriculum
solution stays auditable. The shapes are close enough to drive the
recommender end-to-end.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


class Parallelism(str, Enum):
    DATA_PARALLEL = "data_parallel"  # DDP — replicate model, shard batch
    TENSOR_PARALLEL = "tensor_parallel"  # split tensors across GPUs
    PIPELINE_PARALLEL = "pipeline_parallel"  # split layers across GPUs
    ZERO_1 = "zero_1"  # shard optimizer state
    ZERO_2 = "zero_2"  # shard optimizer state + gradients
    ZERO_3 = "zero_3"  # shard optimizer state + gradients + parameters
    FSDP = "fsdp"  # PyTorch native ZeRO-3-equivalent


# Bytes per parameter in different precision modes. Keep numeric so
# the model-size estimator can compose with optimizer overhead cleanly.
BYTES_PER_PARAM = {
    "fp32": 4,
    "fp16": 2,
    "bf16": 2,
    "fp8": 1,
}

# Optimizer-state overhead is typically the parameter footprint plus
# state tensors. For Adam in fp32 it's: params + momentum + variance =
# 12 bytes/param in master state.
OPTIMIZER_STATE_BYTES_PER_PARAM = {
    "sgd": 0,
    "sgd_momentum": 4,
    "adam": 12,
    "adamw": 12,
    "lion": 8,
}


@dataclass
class HardwareSpec:
    """Cluster shape."""

    gpus_per_node: int = 8
    node_count: int = 4
    gpu_memory_gb: int = 80
    intra_node_bandwidth_gbps: float = 600.0  # NVLink
    inter_node_bandwidth_gbps: float = 200.0  # NVSwitch / IB

    @property
    def total_gpus(self) -> int:
        return self.gpus_per_node * self.node_count

    @property
    def cluster_memory_gb(self) -> int:
        return self.total_gpus * self.gpu_memory_gb


@dataclass
class ModelSpec:
    """Model + training-config sizing parameters."""

    param_count_billions: float
    precision: str = "fp16"  # weights precision
    activation_overhead_gb_per_billion_params: float = 1.5
    optimizer: str = "adam"
    micro_batch_size: int = 8
    sequence_length: int = 2048
    gradient_checkpointing: bool = False

    @property
    def model_size_bytes(self) -> int:
        return int(self.param_count_billions * 1e9 * BYTES_PER_PARAM[self.precision])

    @property
    def model_size_gb(self) -> float:
        return self.model_size_bytes / 1e9

    @property
    def optimizer_state_gb(self) -> float:
        bytes_per = OPTIMIZER_STATE_BYTES_PER_PARAM.get(self.optimizer, 12)
        return self.param_count_billions * 1e9 * bytes_per / 1e9

    @property
    def gradient_gb(self) -> float:
        # Gradients are stored in the same precision as weights.
        return self.model_size_gb

    @property
    def activation_gb(self) -> float:
        # Linear with parameter count; gradient checkpointing halves it.
        base = self.param_count_billions * self.activation_overhead_gb_per_billion_params
        return base * 0.5 if self.gradient_checkpointing else base


@dataclass
class StrategyConfig:
    """One parallelism configuration."""

    parallelism: Parallelism
    data_parallel: int = 1
    tensor_parallel: int = 1
    pipeline_parallel: int = 1

    @property
    def total_gpus(self) -> int:
        return self.data_parallel * self.tensor_parallel * self.pipeline_parallel


@dataclass
class MemoryEstimate:
    """Per-GPU memory breakdown."""

    model_gb: float
    optimizer_gb: float
    gradient_gb: float
    activation_gb: float
    workspace_gb: float = 2.0  # NCCL buffers, kernel temporaries, etc.

    @property
    def total_gb(self) -> float:
        return (
            self.model_gb + self.optimizer_gb + self.gradient_gb
            + self.activation_gb + self.workspace_gb
        )

    def fits(self, gpu_memory_gb: int) -> bool:
        return self.total_gb <= gpu_memory_gb


@dataclass
class ThroughputEstimate:
    """Scaling efficiency estimate."""

    samples_per_second: float
    scaling_efficiency_percent: float
    communication_overhead_percent: float


@dataclass
class StrategyEvaluation:
    """Full evaluation: memory + throughput + recommendation status."""

    config: StrategyConfig
    memory_per_gpu: MemoryEstimate
    throughput: ThroughputEstimate
    feasible: bool
    notes: List[str] = field(default_factory=list)


def estimate_memory(
    model: ModelSpec,
    config: StrategyConfig,
    *,
    hardware: HardwareSpec,
) -> MemoryEstimate:
    """Compute per-GPU memory for the given (model, strategy)."""
    p = config.parallelism

    # How many GPUs the model itself is sharded across.
    model_shards = config.tensor_parallel * config.pipeline_parallel
    if model_shards < 1:
        model_shards = 1

    # Activations are sharded by the same factor that shards the model.
    activation_per_gpu = model.activation_gb / model_shards

    # Gradients + optimizer-state sharding depends on parallelism.
    if p in {Parallelism.DATA_PARALLEL, Parallelism.TENSOR_PARALLEL, Parallelism.PIPELINE_PARALLEL}:
        # Each replica holds full optimizer + gradient.
        model_per_gpu = model.model_size_gb / model_shards
        gradient_per_gpu = model.gradient_gb / model_shards
        optimizer_per_gpu = model.optimizer_state_gb / model_shards
    elif p is Parallelism.ZERO_1:
        # Shard optimizer state across data-parallel rank.
        model_per_gpu = model.model_size_gb / model_shards
        gradient_per_gpu = model.gradient_gb / model_shards
        optimizer_per_gpu = (
            model.optimizer_state_gb / (model_shards * config.data_parallel)
        )
    elif p is Parallelism.ZERO_2:
        model_per_gpu = model.model_size_gb / model_shards
        gradient_per_gpu = (
            model.gradient_gb / (model_shards * config.data_parallel)
        )
        optimizer_per_gpu = (
            model.optimizer_state_gb / (model_shards * config.data_parallel)
        )
    elif p in {Parallelism.ZERO_3, Parallelism.FSDP}:
        shard_factor = model_shards * config.data_parallel
        model_per_gpu = model.model_size_gb / shard_factor
        gradient_per_gpu = model.gradient_gb / shard_factor
        optimizer_per_gpu = model.optimizer_state_gb / shard_factor
    else:
        raise ValueError(f"Unknown parallelism: {p}")

    return MemoryEstimate(
        model_gb=round(model_per_gpu, 3),
        optimizer_gb=round(optimizer_per_gpu, 3),
        gradient_gb=round(gradient_per_gpu, 3),
        activation_gb=round(activation_per_gpu, 3),
    )


def estimate_throughput(
    model: ModelSpec,
    config: StrategyConfig,
    *,
    hardware: HardwareSpec,
    single_gpu_samples_per_sec: float = 6.0,
) -> ThroughputEstimate:
    """Estimate throughput + scaling efficiency for the given strategy."""
    n = config.total_gpus
    p = config.parallelism

    # Base communication overhead by strategy.
    base_overhead = {
        Parallelism.DATA_PARALLEL: 0.08,
        Parallelism.ZERO_1: 0.10,
        Parallelism.ZERO_2: 0.14,
        Parallelism.ZERO_3: 0.22,
        Parallelism.FSDP: 0.20,
        Parallelism.TENSOR_PARALLEL: 0.18,
        Parallelism.PIPELINE_PARALLEL: 0.12,
    }.get(p, 0.15)

    # Tensor parallel scales worst across nodes; penalize when TP spans
    # multiple nodes.
    nodes_for_tp = math.ceil(config.tensor_parallel / hardware.gpus_per_node)
    if config.tensor_parallel > 1 and nodes_for_tp > 1:
        base_overhead += 0.10

    # Pipeline-parallel has a bubble proportional to pipeline depth.
    if config.pipeline_parallel > 1:
        bubble = (config.pipeline_parallel - 1) / config.pipeline_parallel
        base_overhead += bubble * 0.05

    # Scaling efficiency = 1 - overhead, capped at 95%.
    scaling_efficiency = max(0.10, min(0.95, 1.0 - base_overhead))

    # Effective throughput.
    ideal = single_gpu_samples_per_sec * n
    throughput = ideal * scaling_efficiency

    return ThroughputEstimate(
        samples_per_second=round(throughput, 2),
        scaling_efficiency_percent=round(scaling_efficiency * 100.0, 2),
        communication_overhead_percent=round((1.0 - scaling_efficiency) * 100.0, 2),
    )


def evaluate(
    model: ModelSpec,
    config: StrategyConfig,
    *,
    hardware: HardwareSpec,
) -> StrategyEvaluation:
    """Combine memory + throughput estimates with feasibility."""
    if config.total_gpus > hardware.total_gpus:
        return StrategyEvaluation(
            config=config,
            memory_per_gpu=MemoryEstimate(0, 0, 0, 0),
            throughput=ThroughputEstimate(0.0, 0.0, 100.0),
            feasible=False,
            notes=[
                f"Strategy requires {config.total_gpus} GPUs but cluster has "
                f"only {hardware.total_gpus}"
            ],
        )
    memory = estimate_memory(model, config, hardware=hardware)
    throughput = estimate_throughput(model, config, hardware=hardware)
    feasible = memory.fits(hardware.gpu_memory_gb)
    notes: List[str] = []
    if not feasible:
        notes.append(
            f"Per-GPU memory {memory.total_gb:.1f}GB exceeds device capacity "
            f"{hardware.gpu_memory_gb}GB"
        )
    if config.tensor_parallel > hardware.gpus_per_node:
        notes.append(
            "Tensor-parallel group spans multiple nodes; expect significant "
            "communication overhead across InfiniBand/Ethernet."
        )
    return StrategyEvaluation(
        config=config,
        memory_per_gpu=memory,
        throughput=throughput,
        feasible=feasible,
        notes=notes,
    )


# -- Strategy recommender ----------------------------------------------


@dataclass
class RecommendationResult:
    """The recommended strategy + close runners-up."""

    best: StrategyEvaluation
    candidates: List[StrategyEvaluation]
    rationale: str


def recommend_strategy(
    model: ModelSpec,
    hardware: HardwareSpec,
) -> RecommendationResult:
    """Search candidate configurations and pick the highest-throughput
    feasible one."""
    candidates: List[StrategyEvaluation] = []

    # Build a candidate set: pure DDP, ZeRO-1/2/3 + FSDP at full DP,
    # and TP × PP × DP combinations.
    full_dp = StrategyConfig(parallelism=Parallelism.DATA_PARALLEL,
                             data_parallel=hardware.total_gpus)
    candidates.append(evaluate(model, full_dp, hardware=hardware))

    for parallelism in (Parallelism.ZERO_1, Parallelism.ZERO_2,
                        Parallelism.ZERO_3, Parallelism.FSDP):
        config = StrategyConfig(parallelism=parallelism,
                                data_parallel=hardware.total_gpus)
        candidates.append(evaluate(model, config, hardware=hardware))

    # TP × DP combos.
    for tp in (2, 4, 8):
        if tp > hardware.gpus_per_node:
            continue
        if hardware.total_gpus % tp != 0:
            continue
        dp = hardware.total_gpus // tp
        config = StrategyConfig(
            parallelism=Parallelism.TENSOR_PARALLEL,
            data_parallel=dp, tensor_parallel=tp,
        )
        candidates.append(evaluate(model, config, hardware=hardware))

    # PP × DP combos.
    for pp in (2, 4):
        if hardware.total_gpus % pp != 0:
            continue
        dp = hardware.total_gpus // pp
        config = StrategyConfig(
            parallelism=Parallelism.PIPELINE_PARALLEL,
            data_parallel=dp, pipeline_parallel=pp,
        )
        candidates.append(evaluate(model, config, hardware=hardware))

    feasible = [c for c in candidates if c.feasible]
    if not feasible:
        # Suggest the closest-to-feasible (lowest total memory).
        worst = min(candidates, key=lambda c: c.memory_per_gpu.total_gb)
        return RecommendationResult(
            best=worst,
            candidates=sorted(candidates, key=lambda c: c.memory_per_gpu.total_gb),
            rationale=(
                "No configuration fits in GPU memory; consider enabling "
                "gradient_checkpointing or reducing model size / batch."
            ),
        )

    best = max(feasible, key=lambda c: c.throughput.samples_per_second)
    candidates_sorted = sorted(
        candidates,
        key=lambda c: (-int(c.feasible), -c.throughput.samples_per_second),
    )
    return RecommendationResult(
        best=best,
        candidates=candidates_sorted,
        rationale=(
            f"Selected {best.config.parallelism.value} (TP={best.config.tensor_parallel}, "
            f"PP={best.config.pipeline_parallel}, DP={best.config.data_parallel}); "
            f"throughput {best.throughput.samples_per_second:.1f} samples/sec "
            f"at {best.throughput.scaling_efficiency_percent:.1f}% scaling."
        ),
    )
