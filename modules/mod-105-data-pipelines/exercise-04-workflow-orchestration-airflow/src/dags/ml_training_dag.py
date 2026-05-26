"""
ML Training DAG

Assembles the chain validate → engineer → train → register with a
SlackAlertOperator as an on-failure side path. Compatible with Apache
Airflow when deployed there, and runnable in a standalone Python
process (the curriculum default) via `DAG.run()`.

This module:
- Defines the DAG class with topological scheduling.
- Builds the default ML training DAG (`build_ml_training_dag`).
- Provides a sample dataset loader, feature function, and training
  function used by the demo CLI and the test suite.
"""

from __future__ import annotations

import logging
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..operators.custom_operators import (
    DataValidationOperator,
    FeatureEngineeringOperator,
    ModelRegistryOperator,
    ModelTrainingOperator,
    Operator,
    OperatorState,
    SlackAlertOperator,
    TaskInstance,
    TaskRunResult,
)


logger = logging.getLogger(__name__)


@dataclass
class DagRunReport:
    dag_id: str
    started_at: datetime
    ended_at: datetime
    successful_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    skipped_tasks: List[str] = field(default_factory=list)
    results: Dict[str, TaskRunResult] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.failed_tasks

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()


class DAG:
    """Minimal DAG with topological scheduling + downstream skip on failure."""

    def __init__(self, dag_id: str, *, description: str = ""):
        self.dag_id = dag_id
        self.description = description
        self._operators: Dict[str, Operator] = {}
        self._on_failure_targets: Dict[str, List[str]] = {}

    def add(self, operator: Operator) -> Operator:
        if operator.task_id in self._operators:
            raise ValueError(f"Duplicate task_id {operator.task_id!r}")
        self._operators[operator.task_id] = operator
        return operator

    def link_on_failure(self, source_task_id: str, alert_task_id: str) -> None:
        """When `source_task_id` fails, also run `alert_task_id`."""
        self._on_failure_targets.setdefault(source_task_id, []).append(alert_task_id)

    def topological_order(self) -> List[Operator]:
        order: List[Operator] = []
        visited: set[str] = set()

        def _visit(task_id: str) -> None:
            if task_id in visited:
                return
            op = self._operators[task_id]
            for upstream in op.depends_on:
                if upstream not in self._operators:
                    raise ValueError(
                        f"Task {task_id!r} depends on unknown task {upstream!r}"
                    )
                _visit(upstream)
            visited.add(task_id)
            order.append(op)

        for task_id in self._operators:
            _visit(task_id)
        return order

    def run(self, *, dag_run_id: Optional[str] = None) -> DagRunReport:
        dag_run_id = dag_run_id or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        started = datetime.now(timezone.utc)
        ti = TaskInstance(
            task_id="<dag>",
            dag_run_id=dag_run_id,
            logical_date=started,
        )
        report = DagRunReport(dag_id=self.dag_id, started_at=started, ended_at=started)
        failed_tasks: set[str] = set()
        skipped_tasks: set[str] = set()

        # Reverse-index: task → list of upstream sources that wire on-failure.
        alert_sources: Dict[str, List[str]] = {}
        for source, targets in self._on_failure_targets.items():
            for target in targets:
                alert_sources.setdefault(target, []).append(source)

        for operator in self.topological_order():
            is_alert = operator.task_id in alert_sources
            if is_alert:
                # Skip alert tasks unless one of their on-failure sources failed.
                if not any(src in failed_tasks for src in alert_sources[operator.task_id]):
                    skipped_tasks.add(operator.task_id)
                    report.skipped_tasks.append(operator.task_id)
                    report.results[operator.task_id] = TaskRunResult(
                        task_id=operator.task_id,
                        state=OperatorState.SKIPPED,
                        started_at=datetime.now(timezone.utc),
                        ended_at=datetime.now(timezone.utc),
                        attempts=0,
                    )
                    continue
            else:
                # Non-alert tasks: skip if any dep failed OR was skipped.
                blocked = [
                    dep for dep in operator.depends_on
                    if dep in failed_tasks or dep in skipped_tasks
                ]
                if blocked:
                    skipped_tasks.add(operator.task_id)
                    report.skipped_tasks.append(operator.task_id)
                    report.results[operator.task_id] = TaskRunResult(
                        task_id=operator.task_id,
                        state=OperatorState.SKIPPED,
                        started_at=datetime.now(timezone.utc),
                        ended_at=datetime.now(timezone.utc),
                        attempts=0,
                    )
                    continue

            ti.task_id = operator.task_id
            result = operator.run(ti)
            report.results[operator.task_id] = result
            if result.state in {OperatorState.SUCCESS, OperatorState.RETRIED}:
                report.successful_tasks.append(operator.task_id)
            elif result.state is OperatorState.FAILED:
                failed_tasks.add(operator.task_id)
                report.failed_tasks.append(operator.task_id)
                # Record failure context for downstream alert operators.
                ti.push("__last_failure__", {
                    "task_id": operator.task_id,
                    "error": result.error,
                })
        report.ended_at = datetime.now(timezone.utc)
        return report


# -- Sample loaders + training functions --------------------------------


def sample_dataset_loader(_ti: TaskInstance, *, seed: int = 42, row_count: int = 500) -> List[Dict[str, Any]]:
    """Deterministic sample dataset for the demo + tests."""
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    for i in range(row_count):
        rows.append({
            "txn_id": f"tx-{i:06d}",
            "user_id": f"u{rng.randint(1, 1000):05d}",
            "amount": round(rng.expovariate(1 / 50), 2),
            "merchant": rng.choice(["amzn", "wmt", "kr", "tgt"]),
            "label": 1 if rng.random() < 0.02 else 0,  # fraud
        })
    return rows


def sample_feature_fn(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute aggregate features per user."""
    by_user: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_user.setdefault(row["user_id"], []).append(row)
    features: List[Dict[str, Any]] = []
    for user_id, transactions in by_user.items():
        amounts = [t["amount"] for t in transactions]
        labels = [t["label"] for t in transactions]
        features.append({
            "user_id": user_id,
            "txn_count": len(transactions),
            "avg_amount": statistics.mean(amounts) if amounts else 0.0,
            "max_amount": max(amounts) if amounts else 0.0,
            "fraud_label": int(any(labels)),
        })
    return features


def sample_training_fn(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Trivial 'training': compute fraud-rate threshold + accuracy."""
    if not features:
        return {"name": "fraud-detector", "version": "v0", "metrics": {"accuracy": 0.0}}
    fraud = [f for f in features if f["fraud_label"]]
    fraud_rate = len(fraud) / len(features)
    # 'Trained' threshold: avg_amount above which fraud is more likely.
    if fraud:
        threshold = statistics.median([f["avg_amount"] for f in fraud])
    else:
        threshold = float("inf")
    # Synthetic accuracy: 1 - fraud_rate * 0.3.
    accuracy = max(0.0, 1.0 - fraud_rate * 0.3)
    return {
        "name": "fraud-detector",
        "version": f"v{datetime.now(timezone.utc).strftime('%Y%m%d.%H%M%S')}",
        "threshold": round(threshold, 4),
        "metrics": {
            "accuracy": round(accuracy, 4),
            "fraud_rate": round(fraud_rate, 4),
            "feature_count": len(features),
        },
    }


# -- DAG builder --------------------------------------------------------


def build_ml_training_dag(
    *,
    dataset_loader: Optional[Callable[[TaskInstance], List[Dict[str, Any]]]] = None,
    feature_fn: Optional[Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]]] = None,
    training_fn: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]] = None,
    slack_channel: str = "#ml-platform-alerts",
) -> DAG:
    """Build the standard validate → engineer → train → register pipeline."""
    dataset_loader = dataset_loader or sample_dataset_loader
    feature_fn = feature_fn or sample_feature_fn
    training_fn = training_fn or sample_training_fn

    dag = DAG("ml_training", description="Validate, engineer, train, register a model")
    dag.add(DataValidationOperator(
        task_id="validate_data",
        dataset_loader=_attach_xcom("validate_data", dataset_loader),
        min_rows=100,
        max_null_ratio=0.05,
        expected_columns=["txn_id", "user_id", "amount", "label"],
    ))
    dag.add(FeatureEngineeringOperator(
        task_id="engineer_features",
        feature_fn=feature_fn,
        upstream_task_id="validate_data",
    ))
    dag.add(ModelTrainingOperator(
        task_id="train_model",
        training_fn=training_fn,
        feature_task_id="engineer_features",
    ))
    dag.add(ModelRegistryOperator(
        task_id="register_model",
        training_task_id="train_model",
    ))
    dag.add(SlackAlertOperator(
        task_id="alert_on_failure",
        channel=slack_channel,
        depends_on=["validate_data", "engineer_features", "train_model"],
    ))
    # Fan-out alert when any of the upstream tasks fail.
    for upstream in ("validate_data", "engineer_features", "train_model"):
        dag.link_on_failure(upstream, "alert_on_failure")
    return dag


def _attach_xcom(
    task_id: str,
    loader: Callable[[TaskInstance], List[Dict[str, Any]]],
) -> Callable[[TaskInstance], List[Dict[str, Any]]]:
    """Wrap a loader so the dataset is published via XCom for downstream tasks."""
    def _wrapped(ti: TaskInstance) -> List[Dict[str, Any]]:
        rows = loader(ti)
        ti.push(f"{task_id}.dataset", rows)
        return rows
    return _wrapped
