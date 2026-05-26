"""
Distributed Trainer

A small framework-independent trainer that wraps the standard
distributed loop:

- Setup: build groups (DP/TP/PP), allocate state.
- Train loop: forward → backward → all-reduce → optimizer step,
  with periodic checkpointing.
- Failure recovery: if a rank fails, the coordinator restores the
  most recent checkpoint and resumes the loop from the saved step.

The real distributed primitives (NCCL, torch.distributed) are gated
behind a Backend Protocol; an InMemoryBackend simulates the contract
deterministically so unit tests and the CLI demo run without a CUDA
runtime.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from .distributed_strategy import (
    HardwareSpec,
    ModelSpec,
    Parallelism,
    StrategyConfig,
    evaluate,
)


logger = logging.getLogger(__name__)


# -- Distributed backend abstraction -----------------------------------


class Backend(Protocol):
    """Pluggable distributed backend."""

    rank: int
    world_size: int

    def all_reduce(self, value: float, *, op: str = "sum") -> float: ...

    def broadcast(self, value: Any, *, src_rank: int) -> Any: ...

    def barrier(self) -> None: ...

    def is_rank_zero(self) -> bool: ...


class InMemoryBackend:
    """Single-process simulation of multi-rank communication."""

    def __init__(self, *, rank: int = 0, world_size: int = 1):
        self.rank = rank
        self.world_size = world_size
        self._reduce_log: List[Dict[str, Any]] = []

    def all_reduce(self, value: float, *, op: str = "sum") -> float:
        # Simulate identical per-rank values + the requested reduction.
        self._reduce_log.append({"op": op, "value": value})
        if op == "sum":
            return value * self.world_size
        if op == "mean":
            return value
        if op == "max":
            return value
        if op == "min":
            return value
        raise ValueError(f"Unknown reduction op: {op}")

    def broadcast(self, value: Any, *, src_rank: int) -> Any:
        return value

    def barrier(self) -> None:
        return None

    def is_rank_zero(self) -> bool:
        return self.rank == 0

    @property
    def reduce_log(self) -> List[Dict[str, Any]]:
        return list(self._reduce_log)


# -- Trainer state machine + checkpointing ------------------------------


class TrainerState(str, Enum):
    INITIAL = "initial"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class CheckpointMeta:
    step: int
    saved_at: datetime
    path: Path
    metrics: Dict[str, float] = field(default_factory=dict)
    rng_state: Optional[int] = None


@dataclass
class TrainingMetrics:
    """Snapshot of metrics at one step."""

    step: int
    train_loss: float
    samples_per_second: float
    grad_norm: float
    learning_rate: float


@dataclass
class TrainerConfig:
    """Trainer behavior knobs."""

    total_steps: int = 100
    log_every: int = 10
    checkpoint_every: int = 25
    enable_fault_recovery: bool = True
    max_recovery_attempts: int = 3
    rank_zero_only_logging: bool = True


@dataclass
class TrainerReport:
    """Outcome of a training run."""

    state: TrainerState
    steps_completed: int
    metrics_history: List[TrainingMetrics]
    checkpoints: List[CheckpointMeta]
    recoveries: int
    duration_seconds: float
    failure_reason: Optional[str] = None


class DistributedTrainer:
    """Drives the train loop + checkpointing + recovery."""

    def __init__(
        self,
        backend: Backend,
        model: ModelSpec,
        strategy: StrategyConfig,
        hardware: HardwareSpec,
        config: TrainerConfig,
        *,
        train_step_fn: Optional[Callable[[int, "DistributedTrainer"], TrainingMetrics]] = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        checkpoint_dir: Optional[Path] = None,
    ):
        self.backend = backend
        self.model = model
        self.strategy = strategy
        self.hardware = hardware
        self.config = config
        self.train_step_fn = train_step_fn or _default_train_step
        self.clock = clock
        self.checkpoint_dir = checkpoint_dir
        # Mutable training state.
        self.state = TrainerState.INITIAL
        self.current_step = 0
        self.metrics_history: List[TrainingMetrics] = []
        self.checkpoints: List[CheckpointMeta] = []
        self.recoveries = 0

    # -- public API ----------------------------------------------------

    def train(self) -> TrainerReport:
        # Verify the strategy is feasible.
        eval_result = evaluate(self.model, self.strategy, hardware=self.hardware)
        if not eval_result.feasible:
            self.state = TrainerState.FAILED
            return TrainerReport(
                state=self.state, steps_completed=0,
                metrics_history=[], checkpoints=[], recoveries=0,
                duration_seconds=0.0,
                failure_reason="; ".join(eval_result.notes) or "strategy not feasible",
            )

        started = self.clock()
        self.state = TrainerState.RUNNING
        attempts = 0
        while self.current_step < self.config.total_steps:
            try:
                self._step()
            except RuntimeError as exc:
                if not self.config.enable_fault_recovery:
                    self.state = TrainerState.FAILED
                    return self._build_report(started, failure=str(exc))
                attempts += 1
                self.recoveries += 1
                if attempts > self.config.max_recovery_attempts:
                    self.state = TrainerState.FAILED
                    return self._build_report(
                        started,
                        failure=f"Exceeded max recovery attempts ({attempts}): {exc}",
                    )
                logger.warning(
                    "Recovery #%d after error: %s", attempts, exc,
                )
                self._restore_latest_checkpoint()
        self.state = TrainerState.COMPLETED
        return self._build_report(started)

    # -- internals -----------------------------------------------------

    def _step(self) -> None:
        step = self.current_step
        metrics = self.train_step_fn(step, self)
        # All-reduce the loss across data-parallel replicas.
        reduced_loss = self.backend.all_reduce(metrics.train_loss, op="mean")
        metrics = TrainingMetrics(
            step=metrics.step,
            train_loss=reduced_loss,
            samples_per_second=metrics.samples_per_second,
            grad_norm=metrics.grad_norm,
            learning_rate=metrics.learning_rate,
        )
        self.metrics_history.append(metrics)
        self.current_step = step + 1
        if self._should_log(step):
            logger.info(
                "step=%d loss=%.4f sps=%.1f grad_norm=%.4f lr=%.6f",
                metrics.step, metrics.train_loss, metrics.samples_per_second,
                metrics.grad_norm, metrics.learning_rate,
            )
        if self._should_checkpoint(self.current_step):
            self._save_checkpoint(metrics)

    def _should_log(self, step: int) -> bool:
        if self.config.rank_zero_only_logging and not self.backend.is_rank_zero():
            return False
        return (step % self.config.log_every) == 0

    def _should_checkpoint(self, step: int) -> bool:
        if step == 0:
            return False
        return (step % self.config.checkpoint_every) == 0

    def _save_checkpoint(self, metrics: TrainingMetrics) -> CheckpointMeta:
        path = Path(f"checkpoint-step-{self.current_step:06d}.pt")
        if self.checkpoint_dir is not None:
            path = self.checkpoint_dir / path
            if self.backend.is_rank_zero():
                self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    f"step={self.current_step}\n"
                    f"loss={metrics.train_loss}\n"
                    f"grad_norm={metrics.grad_norm}\n"
                )
        meta = CheckpointMeta(
            step=self.current_step,
            saved_at=self.clock(),
            path=path,
            metrics={
                "loss": metrics.train_loss,
                "samples_per_second": metrics.samples_per_second,
            },
        )
        self.checkpoints.append(meta)
        self.backend.barrier()
        return meta

    def _restore_latest_checkpoint(self) -> None:
        if not self.checkpoints:
            self.current_step = 0
            self.metrics_history.clear()
            return
        latest = self.checkpoints[-1]
        # Roll the trainer state back to the checkpointed step. Drop
        # metrics gathered after the checkpoint to avoid duplicates.
        self.current_step = latest.step
        self.metrics_history = [
            m for m in self.metrics_history if m.step < latest.step
        ]
        self.backend.barrier()

    def _build_report(
        self,
        started: datetime,
        *,
        failure: Optional[str] = None,
    ) -> TrainerReport:
        duration = (self.clock() - started).total_seconds()
        if failure:
            self.state = TrainerState.FAILED
        return TrainerReport(
            state=self.state,
            steps_completed=self.current_step,
            metrics_history=list(self.metrics_history),
            checkpoints=list(self.checkpoints),
            recoveries=self.recoveries,
            duration_seconds=duration,
            failure_reason=failure,
        )


# -- default synthetic train step --------------------------------------


def _default_train_step(step: int, trainer: "DistributedTrainer") -> TrainingMetrics:
    """Deterministic synthetic step used by tests + the CLI demo."""
    # Loss decays exponentially with step.
    loss = 2.5 * math.exp(-step / 50.0) + 0.1
    grad_norm = 5.0 / (1.0 + step * 0.05)
    lr = max(1e-5, 3e-4 * (0.99 ** step))
    sps = trainer.strategy.total_gpus * 6.0
    return TrainingMetrics(
        step=step, train_loss=round(loss, 4),
        samples_per_second=round(sps, 1),
        grad_norm=round(grad_norm, 4),
        learning_rate=round(lr, 6),
    )


# -- Fault-injection train step (for testing recovery) -----------------


def make_failing_train_step(
    *,
    fail_at_step: int,
    fail_count: int = 1,
) -> Callable[[int, "DistributedTrainer"], TrainingMetrics]:
    """Wrap the default step so it raises N times at the given step."""
    state = {"remaining_failures": fail_count}

    def step_fn(step: int, trainer: "DistributedTrainer") -> TrainingMetrics:
        if step == fail_at_step and state["remaining_failures"] > 0:
            state["remaining_failures"] -= 1
            raise RuntimeError(
                f"Synthetic NCCL failure at step {step} "
                f"(remaining injected failures: {state['remaining_failures']})"
            )
        return _default_train_step(step, trainer)
    return step_fn
