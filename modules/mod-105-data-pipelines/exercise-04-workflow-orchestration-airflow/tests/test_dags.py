"""Tests for the ML training DAG + custom operators."""

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from src.dags.ml_training_dag import (
    DAG,
    DagRunReport,
    build_ml_training_dag,
    sample_dataset_loader,
    sample_feature_fn,
    sample_training_fn,
)
from src.operators.custom_operators import (
    DataValidationOperator,
    ExternalDataSensor,
    FeatureEngineeringOperator,
    ModelRegistryOperator,
    ModelTrainingOperator,
    Operator,
    OperatorState,
    SlackAlertOperator,
    TaskInstance,
    TaskRunResult,
)


class _CountingOperator(Operator):
    """Test helper: succeeds on the Nth attempt."""

    def __init__(self, task_id: str, *, succeed_on: int, retries: int = 3):
        super().__init__(task_id, retries=retries)
        self.succeed_on = succeed_on
        self.calls = 0

    def execute(self, ti: TaskInstance) -> str:
        self.calls += 1
        if self.calls < self.succeed_on:
            raise RuntimeError(f"intentional failure on attempt {self.calls}")
        return f"ok-{self.calls}"


def _ti(task_id: str = "task") -> TaskInstance:
    return TaskInstance(
        task_id=task_id,
        dag_run_id="run-1",
        logical_date=datetime.now(timezone.utc),
    )


class TestOperatorBase:
    def test_run_records_success(self):
        op = _CountingOperator("t", succeed_on=1, retries=0)
        result = op.run(_ti())
        assert result.state is OperatorState.SUCCESS
        assert result.attempts == 1
        assert result.return_value == "ok-1"

    def test_retries_until_success(self):
        op = _CountingOperator("t", succeed_on=3, retries=3)
        result = op.run(_ti())
        assert result.state is OperatorState.RETRIED
        assert result.attempts == 3

    def test_fails_after_max_retries(self):
        op = _CountingOperator("t", succeed_on=999, retries=2)
        result = op.run(_ti())
        assert result.state is OperatorState.FAILED
        assert result.attempts == 3
        assert "intentional failure" in (result.error or "")

    def test_on_failure_callback_invoked(self):
        captured: List[BaseException] = []
        op = _CountingOperator("t", succeed_on=999, retries=0)
        op.on_failure = lambda ti, exc: captured.append(exc)
        op.run(_ti())
        assert captured
        assert isinstance(captured[0], RuntimeError)


class TestDataValidationOperator:
    def _loader(self, rows: List[Dict[str, Any]]):
        return lambda ti: rows

    def test_passes_with_clean_data(self):
        rows = [{"a": 1, "b": 2, "label": 0} for _ in range(200)]
        op = DataValidationOperator(
            task_id="validate",
            dataset_loader=self._loader(rows),
            min_rows=100,
            expected_columns=["a", "b", "label"],
        )
        result = op.run(_ti("validate"))
        assert result.state is OperatorState.SUCCESS
        assert result.return_value.passed

    def test_fails_on_low_row_count(self):
        rows = [{"a": 1}] * 5
        op = DataValidationOperator(
            task_id="validate",
            dataset_loader=self._loader(rows),
            min_rows=100,
            retries=0,
        )
        result = op.run(_ti("validate"))
        assert result.state is OperatorState.FAILED

    def test_fails_on_excess_nulls(self):
        rows = [{"a": None, "b": None}] * 200
        op = DataValidationOperator(
            task_id="validate",
            dataset_loader=self._loader(rows),
            min_rows=100,
            max_null_ratio=0.05,
            retries=0,
        )
        result = op.run(_ti("validate"))
        assert result.state is OperatorState.FAILED

    def test_fails_on_schema_mismatch(self):
        rows = [{"a": 1}] * 200
        op = DataValidationOperator(
            task_id="validate",
            dataset_loader=self._loader(rows),
            expected_columns=["a", "missing_column"],
            min_rows=100,
            retries=0,
        )
        result = op.run(_ti("validate"))
        assert result.state is OperatorState.FAILED


class TestFeatureAndTrain:
    def test_feature_engineering_consumes_upstream_dataset(self):
        ti = _ti("engineer")
        ti.push("validate.dataset", [{"a": 1}, {"a": 2}])
        op = FeatureEngineeringOperator(
            task_id="engineer",
            feature_fn=lambda rows: [{"sum_a": sum(r["a"] for r in rows)}],
            upstream_task_id="validate",
        )
        result = op.run(ti)
        assert result.state is OperatorState.SUCCESS
        assert ti.pull("engineer.features") == [{"sum_a": 3}]

    def test_training_consumes_features(self):
        ti = _ti("train")
        ti.push("engineer.features", [{"feature": 1}, {"feature": 2}])
        op = ModelTrainingOperator(
            task_id="train",
            training_fn=lambda features: {"name": "test", "version": "v1", "rows": len(features)},
            feature_task_id="engineer",
        )
        result = op.run(ti)
        assert result.state is OperatorState.SUCCESS
        assert ti.pull("train.model")["rows"] == 2

    def test_training_without_features_fails(self):
        op = ModelTrainingOperator(
            task_id="train",
            training_fn=lambda features: {"name": "test"},
            feature_task_id="engineer",
            retries=0,
        )
        result = op.run(_ti("train"))
        assert result.state is OperatorState.FAILED


class TestRegistryOperator:
    def test_registers_model(self):
        ti = _ti("register")
        ti.push("train.model", {"name": "fraud-v1", "version": "v1.0", "metrics": {"acc": 0.9}})
        op = ModelRegistryOperator(
            task_id="register", training_task_id="train", registry_url="http://reg",
        )
        result = op.run(ti)
        assert result.state is OperatorState.SUCCESS
        record = ti.pull("register.registered")
        assert record["name"] == "fraud-v1"
        assert len(op.registered) == 1


class TestSensor:
    def test_sensor_succeeds_when_check_returns_true(self):
        op = ExternalDataSensor(
            task_id="sensor", poke_fn=lambda: True,
            timeout_seconds=1, poke_interval_seconds=1.0,
        )
        result = op.run(_ti("sensor"))
        assert result.state is OperatorState.SUCCESS

    def test_sensor_times_out(self):
        op = ExternalDataSensor(
            task_id="sensor", poke_fn=lambda: False,
            timeout_seconds=1, poke_interval_seconds=1.0,
        )
        result = op.run(_ti("sensor"))
        assert result.state is OperatorState.FAILED
        assert "timed out" in result.error.lower()


class TestDAGScheduling:
    def test_topological_order(self):
        dag = build_ml_training_dag()
        order = [op.task_id for op in dag.topological_order()]
        assert order.index("validate_data") < order.index("engineer_features")
        assert order.index("engineer_features") < order.index("train_model")
        assert order.index("train_model") < order.index("register_model")

    def test_full_dag_runs_to_completion(self):
        dag = build_ml_training_dag()
        report = dag.run()
        assert report.passed
        assert set(report.successful_tasks) == {
            "validate_data", "engineer_features", "train_model", "register_model",
        }

    def test_failure_triggers_alert_and_skip(self):
        # Force validation to fail with a too-small dataset.
        def _loader(ti):
            return [{"txn_id": "x", "user_id": "u", "amount": 1, "label": 0}]

        dag = build_ml_training_dag(dataset_loader=_loader)
        report = dag.run()
        assert "validate_data" in report.failed_tasks
        assert "engineer_features" in report.skipped_tasks
        assert "train_model" in report.skipped_tasks
        assert "alert_on_failure" in report.successful_tasks
        # Alert payload was recorded.
        alert = dag._operators["alert_on_failure"]
        assert alert.sent

    def test_duplicate_task_id_rejected(self):
        dag = DAG("x")
        dag.add(_CountingOperator("dup", succeed_on=1))
        with pytest.raises(ValueError):
            dag.add(_CountingOperator("dup", succeed_on=1))

    def test_unknown_dependency_rejected(self):
        dag = DAG("x")
        class _NeedsMissing(Operator):
            def execute(self, ti):
                return None
        dag.add(_NeedsMissing("t1", depends_on=["nope"]))
        with pytest.raises(ValueError):
            dag.topological_order()


class TestSampleHelpers:
    def test_sample_dataset_is_deterministic(self):
        a = sample_dataset_loader(_ti(), seed=42, row_count=50)
        b = sample_dataset_loader(_ti(), seed=42, row_count=50)
        assert a == b

    def test_sample_feature_fn_groups_by_user(self):
        rows = [{"user_id": "u1", "amount": 10, "label": 0, "merchant": "amzn", "txn_id": "1"}] * 3
        features = sample_feature_fn(rows)
        assert len(features) == 1
        assert features[0]["txn_count"] == 3

    def test_sample_training_fn_handles_empty(self):
        model = sample_training_fn([])
        assert model["metrics"]["accuracy"] == 0.0
