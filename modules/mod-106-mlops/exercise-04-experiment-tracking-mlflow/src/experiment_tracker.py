"""
Experiment Tracker

MLflow-compatible experiment tracker that records hyperparameters,
metrics (single values and time-series), tags, and artifact paths for
each training run. The backend is a Protocol so callers can wire in a
real MLflow client; the in-memory implementation ships with this module
for tests + the CLI demo.

The auto_log() context manager captures the typical training-loop
pattern: log params at start, metrics each epoch, status on exit.
"""

from __future__ import annotations

import json
import logging
import statistics
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol


logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    KILLED = "KILLED"


@dataclass
class MetricEntry:
    """One time-series sample for a metric."""

    value: float
    step: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Run:
    """Captures everything recorded under one experiment run."""

    run_id: str
    experiment_id: str
    experiment_name: str
    status: RunStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    params: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, List[MetricEntry]] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    user: str = "unknown"

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()

    def latest_metric(self, name: str) -> Optional[float]:
        entries = self.metrics.get(name)
        if not entries:
            return None
        return entries[-1].value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "status": self.status.value,
            "user": self.user,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "params": dict(self.params),
            "tags": dict(self.tags),
            "metrics": {
                name: [{"value": e.value, "step": e.step,
                        "timestamp": e.timestamp.isoformat()}
                       for e in entries]
                for name, entries in self.metrics.items()
            },
            "artifacts": list(self.artifacts),
        }


@dataclass
class Experiment:
    """Logical group of runs."""

    experiment_id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    runs: List[Run] = field(default_factory=list)


class TrackingBackend(Protocol):
    """Pluggable tracking-server abstraction."""

    def create_experiment(self, name: str) -> Experiment: ...

    def get_experiment(self, name: str) -> Optional[Experiment]: ...

    def list_experiments(self) -> List[Experiment]: ...

    def create_run(self, experiment_id: str, *, user: str) -> Run: ...

    def update_run(self, run: Run) -> None: ...

    def get_run(self, run_id: str) -> Optional[Run]: ...

    def list_runs(self, experiment_id: str) -> List[Run]: ...


class InMemoryTrackingBackend:
    """Reference backend used in tests + the CLI."""

    def __init__(self, *, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self._experiments: Dict[str, Experiment] = {}
        self._experiments_by_name: Dict[str, str] = {}
        self._runs: Dict[str, Run] = {}
        self._clock = clock
        self._next_run_id = 0

    def create_experiment(self, name: str) -> Experiment:
        if name in self._experiments_by_name:
            return self._experiments[self._experiments_by_name[name]]
        experiment_id = f"exp-{len(self._experiments) + 1:04d}"
        experiment = Experiment(experiment_id=experiment_id, name=name, created_at=self._clock())
        self._experiments[experiment_id] = experiment
        self._experiments_by_name[name] = experiment_id
        return experiment

    def get_experiment(self, name: str) -> Optional[Experiment]:
        experiment_id = self._experiments_by_name.get(name)
        return self._experiments.get(experiment_id) if experiment_id else None

    def list_experiments(self) -> List[Experiment]:
        return sorted(self._experiments.values(), key=lambda e: e.created_at)

    def create_run(self, experiment_id: str, *, user: str) -> Run:
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise KeyError(f"Unknown experiment {experiment_id}")
        self._next_run_id += 1
        run = Run(
            run_id=f"run-{self._next_run_id:06d}",
            experiment_id=experiment_id,
            experiment_name=experiment.name,
            status=RunStatus.RUNNING,
            started_at=self._clock(),
            user=user,
        )
        self._runs[run.run_id] = run
        experiment.runs.append(run)
        return run

    def update_run(self, run: Run) -> None:
        self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[Run]:
        return self._runs.get(run_id)

    def list_runs(self, experiment_id: str) -> List[Run]:
        return sorted(
            (r for r in self._runs.values() if r.experiment_id == experiment_id),
            key=lambda r: r.started_at,
        )


# -- Tracker --------------------------------------------------------------


class ExperimentTracker:
    """High-level API: experiment + run management with auto-logging."""

    def __init__(
        self,
        backend: Optional[TrackingBackend] = None,
        *,
        default_user: str = "user",
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.backend = backend or InMemoryTrackingBackend(clock=clock)
        self.default_user = default_user
        self._clock = clock

    def ensure_experiment(self, name: str) -> Experiment:
        existing = self.backend.get_experiment(name)
        if existing is not None:
            return existing
        return self.backend.create_experiment(name)

    def start_run(self, experiment_name: str, *, user: Optional[str] = None) -> Run:
        experiment = self.ensure_experiment(experiment_name)
        return self.backend.create_run(experiment.experiment_id, user=user or self.default_user)

    def end_run(self, run: Run, *, status: RunStatus = RunStatus.FINISHED) -> Run:
        run.status = status
        run.ended_at = self._clock()
        self.backend.update_run(run)
        return run

    def log_param(self, run: Run, key: str, value: Any) -> None:
        run.params[key] = value
        self.backend.update_run(run)

    def log_params(self, run: Run, params: Dict[str, Any]) -> None:
        run.params.update(params)
        self.backend.update_run(run)

    def log_metric(self, run: Run, key: str, value: float, *, step: int = 0) -> None:
        run.metrics.setdefault(key, []).append(MetricEntry(
            value=float(value), step=step, timestamp=self._clock(),
        ))
        self.backend.update_run(run)

    def log_tag(self, run: Run, key: str, value: str) -> None:
        run.tags[key] = value
        self.backend.update_run(run)

    def log_artifact(self, run: Run, path: str) -> None:
        run.artifacts.append(path)
        self.backend.update_run(run)

    @contextmanager
    def auto_log(
        self,
        experiment_name: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        user: Optional[str] = None,
    ) -> Iterator[Run]:
        run = self.start_run(experiment_name, user=user)
        if params:
            self.log_params(run, params)
        if tags:
            for key, value in tags.items():
                self.log_tag(run, key, value)
        try:
            yield run
        except BaseException as exc:
            self.log_tag(run, "exception.type", type(exc).__name__)
            self.log_tag(run, "exception.message", str(exc))
            self.end_run(run, status=RunStatus.FAILED)
            raise
        else:
            self.end_run(run, status=RunStatus.FINISHED)

    # -- comparison helpers --------------------------------------------

    def compare_runs(
        self,
        experiment_name: str,
        metric: str,
        *,
        sort_descending: bool = True,
    ) -> List[Run]:
        experiment = self.backend.get_experiment(experiment_name)
        if experiment is None:
            return []
        runs = self.backend.list_runs(experiment.experiment_id)
        runs = [r for r in runs if r.status is RunStatus.FINISHED and r.latest_metric(metric) is not None]
        runs.sort(key=lambda r: r.latest_metric(metric), reverse=sort_descending)
        return runs

    def best_run(
        self,
        experiment_name: str,
        metric: str,
        *,
        higher_is_better: bool = True,
    ) -> Optional[Run]:
        runs = self.compare_runs(experiment_name, metric, sort_descending=higher_is_better)
        return runs[0] if runs else None

    def export_runs_to_json(self, experiment_name: str, path: Path) -> int:
        """Persist all runs of an experiment as JSON. Returns count written."""
        experiment = self.backend.get_experiment(experiment_name)
        if experiment is None:
            return 0
        runs = self.backend.list_runs(experiment.experiment_id)
        path.write_text(json.dumps([r.to_dict() for r in runs], indent=2))
        return len(runs)
