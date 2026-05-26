"""
Custom Operators

Airflow-compatible operator implementations for ML workflows. Each
operator inherits from a small Operator base class so the DAGs in
ml_training_dag.py can be exercised in a runtime-independent way
(unit tests + the demo CLI run them without Apache Airflow installed).

When deployed to a real Airflow scheduler, each Operator's `execute()`
method is what Airflow calls. The base class deliberately mirrors the
Airflow interface (execute(context) returns a value passed via XCom).
"""

from __future__ import annotations

import logging
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol


logger = logging.getLogger(__name__)


class OperatorState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRIED = "retried"
    SKIPPED = "skipped"


@dataclass
class TaskInstance:
    """Runtime context passed to Operator.execute()."""

    task_id: str
    dag_run_id: str
    logical_date: datetime
    xcom: Dict[str, Any] = field(default_factory=dict)

    def push(self, key: str, value: Any) -> None:
        self.xcom[key] = value

    def pull(self, key: str, default: Any = None) -> Any:
        return self.xcom.get(key, default)


@dataclass
class TaskRunResult:
    """Outcome of one operator execution."""

    task_id: str
    state: OperatorState
    started_at: datetime
    ended_at: datetime
    attempts: int
    return_value: Any = None
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


class Operator:
    """Base class with retry + alerting behavior."""

    def __init__(
        self,
        task_id: str,
        *,
        retries: int = 3,
        retry_delay_seconds: float = 0.0,
        retry_backoff_factor: float = 2.0,
        depends_on: Optional[List[str]] = None,
        on_failure: Optional[Callable[[TaskInstance, BaseException], None]] = None,
    ):
        self.task_id = task_id
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_backoff_factor = retry_backoff_factor
        self.depends_on = list(depends_on or [])
        self.on_failure = on_failure

    def execute(self, ti: TaskInstance) -> Any:
        raise NotImplementedError

    def run(self, ti: TaskInstance) -> TaskRunResult:
        started = datetime.now(timezone.utc)
        attempt = 0
        while True:
            attempt += 1
            try:
                value = self.execute(ti)
                return TaskRunResult(
                    task_id=self.task_id,
                    state=OperatorState.RETRIED if attempt > 1 else OperatorState.SUCCESS,
                    started_at=started,
                    ended_at=datetime.now(timezone.utc),
                    attempts=attempt,
                    return_value=value,
                )
            except Exception as exc:
                if attempt > self.retries:
                    if self.on_failure is not None:
                        self.on_failure(ti, exc)
                    return TaskRunResult(
                        task_id=self.task_id,
                        state=OperatorState.FAILED,
                        started_at=started,
                        ended_at=datetime.now(timezone.utc),
                        attempts=attempt,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                delay = self.retry_delay_seconds * (self.retry_backoff_factor ** (attempt - 1))
                if delay > 0:
                    time.sleep(delay)


# -- Concrete ML operators ----------------------------------------------


@dataclass
class DataValidationResult:
    """Output of the data-validation operator."""

    row_count: int
    null_ratio: float
    schema_match: bool
    sample_hash: str
    passed: bool
    errors: List[str] = field(default_factory=list)


class DataValidationOperator(Operator):
    """Validate that a dataset meets quality thresholds."""

    def __init__(
        self,
        task_id: str,
        *,
        dataset_loader: Callable[[TaskInstance], List[Dict[str, Any]]],
        min_rows: int = 100,
        max_null_ratio: float = 0.05,
        expected_columns: Optional[List[str]] = None,
        retries: int = 3,
        on_failure: Optional[Callable[[TaskInstance, BaseException], None]] = None,
    ):
        super().__init__(task_id, retries=retries, on_failure=on_failure)
        self.loader = dataset_loader
        self.min_rows = min_rows
        self.max_null_ratio = max_null_ratio
        self.expected_columns = expected_columns or []

    def execute(self, ti: TaskInstance) -> DataValidationResult:
        rows = self.loader(ti)
        errors: List[str] = []
        if len(rows) < self.min_rows:
            errors.append(f"row_count {len(rows)} < {self.min_rows}")
        nulls = 0
        cells = 0
        for row in rows:
            for value in row.values():
                cells += 1
                if value is None:
                    nulls += 1
        null_ratio = nulls / cells if cells else 0.0
        if null_ratio > self.max_null_ratio:
            errors.append(f"null_ratio {null_ratio:.3f} > {self.max_null_ratio}")
        schema_match = True
        if self.expected_columns and rows:
            observed = set(rows[0].keys())
            missing = set(self.expected_columns) - observed
            if missing:
                schema_match = False
                errors.append(f"missing columns: {sorted(missing)}")
        sample_hash = _stable_hash(rows[:5]) if rows else "0"

        result = DataValidationResult(
            row_count=len(rows),
            null_ratio=null_ratio,
            schema_match=schema_match,
            sample_hash=sample_hash,
            passed=not errors,
            errors=errors,
        )
        ti.push(f"{self.task_id}.result", result)
        if not result.passed:
            raise RuntimeError(f"Validation failed: {'; '.join(errors)}")
        return result


class FeatureEngineeringOperator(Operator):
    """Compute features from a validated dataset."""

    def __init__(
        self,
        task_id: str,
        *,
        feature_fn: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
        upstream_task_id: str,
        retries: int = 3,
    ):
        super().__init__(task_id, retries=retries, depends_on=[upstream_task_id])
        self.feature_fn = feature_fn
        self.upstream_task_id = upstream_task_id

    def execute(self, ti: TaskInstance) -> List[Dict[str, Any]]:
        rows = ti.pull(f"{self.upstream_task_id}.dataset", [])
        if not rows:
            raise RuntimeError(f"No upstream dataset from {self.upstream_task_id}")
        features = self.feature_fn(rows)
        ti.push(f"{self.task_id}.features", features)
        return features


class ModelTrainingOperator(Operator):
    """Train a model. The actual training is a callable so this operator
    is independent of the ML framework choice (sklearn, PyTorch, ...).
    """

    def __init__(
        self,
        task_id: str,
        *,
        training_fn: Callable[[List[Dict[str, Any]]], Dict[str, Any]],
        feature_task_id: str,
        retries: int = 3,
    ):
        super().__init__(task_id, retries=retries, depends_on=[feature_task_id])
        self.training_fn = training_fn
        self.feature_task_id = feature_task_id

    def execute(self, ti: TaskInstance) -> Dict[str, Any]:
        features = ti.pull(f"{self.feature_task_id}.features", [])
        if not features:
            raise RuntimeError(f"No features from {self.feature_task_id}")
        model = self.training_fn(features)
        ti.push(f"{self.task_id}.model", model)
        return model


class ModelRegistryOperator(Operator):
    """Register a trained model in a model registry."""

    def __init__(
        self,
        task_id: str,
        *,
        training_task_id: str,
        registry_url: str = "http://model-registry/api",
        retries: int = 3,
    ):
        super().__init__(task_id, retries=retries, depends_on=[training_task_id])
        self.training_task_id = training_task_id
        self.registry_url = registry_url
        self.registered: List[Dict[str, Any]] = []  # demo log

    def execute(self, ti: TaskInstance) -> Dict[str, Any]:
        model = ti.pull(f"{self.training_task_id}.model", {})
        if not model:
            raise RuntimeError("No model to register")
        record = {
            "name": model.get("name", "unknown"),
            "version": model.get("version", "v0"),
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "registry": self.registry_url,
            "metrics": model.get("metrics", {}),
        }
        self.registered.append(record)
        ti.push(f"{self.task_id}.registered", record)
        return record


class SlackAlertOperator(Operator):
    """Pushes a structured alert when an upstream task fails."""

    def __init__(
        self,
        task_id: str,
        *,
        channel: str,
        depends_on: Optional[List[str]] = None,
        sender: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__(task_id, retries=0, depends_on=depends_on)
        self.channel = channel
        self.sender = sender or (lambda payload: None)
        self.sent: List[Dict[str, Any]] = []

    def execute(self, ti: TaskInstance) -> Dict[str, Any]:
        failed = ti.pull("__last_failure__")
        if not failed:
            return {"sent": False, "reason": "no failure to report"}
        payload = {
            "channel": self.channel,
            "message": failed,
            "dag_run_id": ti.dag_run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.sender(payload)
        self.sent.append(payload)
        return {"sent": True, "channel": self.channel}


class ExternalDataSensor(Operator):
    """Polls an external check until it returns True or times out."""

    def __init__(
        self,
        task_id: str,
        *,
        poke_fn: Callable[[], bool],
        timeout_seconds: int = 60,
        poke_interval_seconds: float = 1.0,
    ):
        super().__init__(task_id, retries=0)
        self.poke_fn = poke_fn
        self.timeout_seconds = timeout_seconds
        self.poke_interval_seconds = poke_interval_seconds

    def execute(self, ti: TaskInstance) -> bool:
        # Operate on a logical "tick" budget for testability.
        max_pokes = max(1, int(self.timeout_seconds / max(self.poke_interval_seconds, 0.001)))
        for _ in range(max_pokes):
            if self.poke_fn():
                return True
        raise TimeoutError(f"Sensor {self.task_id} timed out after {max_pokes} pokes")


# -- helpers -----------------------------------------------------------


def _stable_hash(rows: List[Dict[str, Any]]) -> str:
    """Cheap deterministic hash of a row sample for dataset versioning."""
    import json
    payload = json.dumps(rows, sort_keys=True, default=str)
    h = 0
    for ch in payload:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"
