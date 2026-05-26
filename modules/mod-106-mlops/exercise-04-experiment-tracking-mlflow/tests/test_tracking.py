"""Tests for the experiment tracker + model registry."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from src.experiment_tracker import (
    ExperimentTracker,
    InMemoryTrackingBackend,
    Run,
    RunStatus,
)
from src.model_registry import (
    ABComparison,
    ModelRegistry,
    PromotionPolicy,
    RegistryError,
    Stage,
    auto_promote,
    compare_versions,
    make_version_from_run,
)


@pytest.fixture
def tracker() -> ExperimentTracker:
    return ExperimentTracker(default_user="tester")


@pytest.fixture
def registry() -> ModelRegistry:
    return ModelRegistry()


class TestExperimentTracker:
    def test_ensure_experiment_idempotent(self, tracker):
        a = tracker.ensure_experiment("fraud")
        b = tracker.ensure_experiment("fraud")
        assert a.experiment_id == b.experiment_id

    def test_run_lifecycle(self, tracker):
        run = tracker.start_run("fraud")
        assert run.status is RunStatus.RUNNING
        tracker.log_param(run, "lr", 0.001)
        tracker.log_metric(run, "accuracy", 0.85)
        tracker.end_run(run)
        assert run.status is RunStatus.FINISHED
        assert run.ended_at is not None
        assert run.params == {"lr": 0.001}
        assert run.latest_metric("accuracy") == 0.85

    def test_log_metric_history(self, tracker):
        run = tracker.start_run("fraud")
        for step, value in enumerate([0.7, 0.75, 0.82, 0.88]):
            tracker.log_metric(run, "accuracy", value, step=step)
        assert len(run.metrics["accuracy"]) == 4
        assert run.latest_metric("accuracy") == 0.88

    def test_auto_log_finishes_on_success(self, tracker):
        with tracker.auto_log("fraud", params={"lr": 0.001}, tags={"env": "dev"}) as run:
            tracker.log_metric(run, "accuracy", 0.9)
        completed = tracker.backend.get_run(run.run_id)
        assert completed.status is RunStatus.FINISHED
        assert completed.tags == {"env": "dev"}

    def test_auto_log_marks_failed_on_exception(self, tracker):
        with pytest.raises(RuntimeError):
            with tracker.auto_log("fraud") as run:
                raise RuntimeError("training boom")
        completed = tracker.backend.get_run(run.run_id)
        assert completed.status is RunStatus.FAILED
        assert completed.tags["exception.type"] == "RuntimeError"
        assert "training boom" in completed.tags["exception.message"]

    def test_compare_runs_orders_by_metric(self, tracker):
        for accuracy in [0.7, 0.85, 0.92, 0.88]:
            with tracker.auto_log("fraud") as run:
                tracker.log_metric(run, "accuracy", accuracy)
        ordered = tracker.compare_runs("fraud", "accuracy")
        assert [r.latest_metric("accuracy") for r in ordered] == [0.92, 0.88, 0.85, 0.7]

    def test_best_run_picks_highest(self, tracker):
        for accuracy in [0.7, 0.85, 0.92]:
            with tracker.auto_log("fraud") as run:
                tracker.log_metric(run, "accuracy", accuracy)
        best = tracker.best_run("fraud", "accuracy")
        assert best.latest_metric("accuracy") == 0.92

    def test_best_run_lower_is_better(self, tracker):
        for loss in [0.5, 0.1, 0.3]:
            with tracker.auto_log("fraud") as run:
                tracker.log_metric(run, "loss", loss)
        best = tracker.best_run("fraud", "loss", higher_is_better=False)
        assert best.latest_metric("loss") == 0.1

    def test_export_runs_to_json(self, tracker, tmp_path: Path):
        for _ in range(3):
            with tracker.auto_log("fraud") as run:
                tracker.log_metric(run, "accuracy", 0.9)
        path = tmp_path / "runs.json"
        count = tracker.export_runs_to_json("fraud", path)
        assert count == 3
        assert path.exists()
        import json
        records = json.loads(path.read_text())
        assert len(records) == 3
        assert records[0]["status"] == "FINISHED"


class TestModelRegistry:
    def test_register_creates_first_version(self, registry):
        v = registry.register(
            model_name="m", artifact_uri="s3://m/v1", run_id="r1",
            metrics={"accuracy": 0.9},
        )
        assert v.version == 1
        assert v.stage is Stage.NONE

    def test_register_increments_versions(self, registry):
        v1 = registry.register(model_name="m", artifact_uri="s3://m/v1", run_id="r1")
        v2 = registry.register(model_name="m", artifact_uri="s3://m/v2", run_id="r2")
        v3 = registry.register(model_name="m", artifact_uri="s3://m/v3", run_id="r3")
        assert (v1.version, v2.version, v3.version) == (1, 2, 3)

    def test_transition_archives_previous_production(self, registry):
        registry.register(model_name="m", artifact_uri="s3://1", run_id="r1")
        registry.register(model_name="m", artifact_uri="s3://2", run_id="r2")
        registry.transition("m", 1, Stage.PRODUCTION, actor="t")
        registry.transition("m", 2, Stage.PRODUCTION, actor="t")
        assert registry.get("m", 1).stage is Stage.ARCHIVED
        assert registry.get("m", 2).stage is Stage.PRODUCTION

    def test_only_one_production_at_a_time(self, registry):
        registry.register(model_name="m", artifact_uri="s3://1", run_id="r1")
        registry.register(model_name="m", artifact_uri="s3://2", run_id="r2")
        registry.transition("m", 1, Stage.PRODUCTION, actor="t")
        registry.transition("m", 2, Stage.PRODUCTION, actor="t")
        prods = registry.list_versions("m", stage=Stage.PRODUCTION)
        assert len(prods) == 1

    def test_transition_records_audit_log(self, registry):
        registry.register(model_name="m", artifact_uri="s3://1", run_id="r1")
        registry.transition("m", 1, Stage.STAGING, actor="alice", reason="ready for QA")
        registry.transition("m", 1, Stage.PRODUCTION, actor="alice", reason="deploy")
        history = [t for t in registry.transitions if t.model_name == "m"]
        assert len(history) == 2
        assert history[0].actor == "alice"

    def test_rollback_restores_previous_production(self, registry):
        registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                          metrics={"accuracy": 0.9})
        registry.register(model_name="m", artifact_uri="s3://2", run_id="r2",
                          metrics={"accuracy": 0.92})
        registry.transition("m", 1, Stage.PRODUCTION, actor="ci", reason="deploy v1")
        registry.transition("m", 2, Stage.PRODUCTION, actor="ci", reason="deploy v2")
        rolled = registry.rollback("m", actor="oncall")
        assert rolled.version == 1
        assert rolled.stage is Stage.PRODUCTION
        assert registry.get("m", 2).stage is Stage.ARCHIVED

    def test_rollback_without_previous_raises(self, registry):
        registry.register(model_name="m", artifact_uri="s3://1", run_id="r1")
        registry.transition("m", 1, Stage.PRODUCTION, actor="t")
        with pytest.raises(RegistryError):
            registry.rollback("m")

    def test_get_unknown_raises(self, registry):
        with pytest.raises(RegistryError):
            registry.get("nope", 1)

    def test_lineage_includes_transitions_and_run_id(self, registry):
        registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                          metrics={"accuracy": 0.9})
        registry.transition("m", 1, Stage.STAGING)
        registry.transition("m", 1, Stage.PRODUCTION)
        lineage = registry.lineage("m", 1)
        assert lineage["run_id"] == "r1"
        assert lineage["current_stage"] == "Production"
        assert len(lineage["transitions"]) == 2


class TestPromotionPolicy:
    def test_promotes_with_clear_improvement(self):
        registry = ModelRegistry()
        incumbent = registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                                      metrics={"accuracy": 0.85, "fairness_score": 0.9})
        registry.transition("m", 1, Stage.PRODUCTION)
        candidate = registry.register(model_name="m", artifact_uri="s3://2", run_id="r2",
                                      metrics={"accuracy": 0.91, "fairness_score": 0.92})
        decision = auto_promote(registry, candidate, PromotionPolicy(metric="accuracy"))
        assert decision.promote
        assert registry.get("m", 2).stage is Stage.PRODUCTION

    def test_rejects_marginal_improvement(self):
        registry = ModelRegistry()
        incumbent = registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                                      metrics={"accuracy": 0.90})
        registry.transition("m", 1, Stage.PRODUCTION)
        candidate = registry.register(model_name="m", artifact_uri="s3://2", run_id="r2",
                                      metrics={"accuracy": 0.9005})
        decision = auto_promote(registry, candidate,
                                PromotionPolicy(metric="accuracy", min_improvement=0.01))
        assert not decision.promote

    def test_rejects_on_secondary_regression(self):
        registry = ModelRegistry()
        registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                          metrics={"accuracy": 0.85, "fairness_score": 0.95})
        registry.transition("m", 1, Stage.PRODUCTION)
        candidate = registry.register(model_name="m", artifact_uri="s3://2", run_id="r2",
                                      metrics={"accuracy": 0.91, "fairness_score": 0.80})
        policy = PromotionPolicy(metric="accuracy",
                                 forbid_regression_in=["fairness_score"])
        decision = auto_promote(registry, candidate, policy)
        assert not decision.promote
        assert "fairness_score" in decision.reason

    def test_require_min_value(self):
        registry = ModelRegistry()
        candidate = registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                                      metrics={"accuracy": 0.4})
        policy = PromotionPolicy(metric="accuracy", require_min_value=0.7)
        decision = auto_promote(registry, candidate, policy)
        assert not decision.promote

    def test_promotes_when_no_incumbent(self):
        registry = ModelRegistry()
        candidate = registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                                      metrics={"accuracy": 0.9})
        decision = auto_promote(registry, candidate, PromotionPolicy(metric="accuracy"))
        assert decision.promote
        assert registry.get("m", 1).stage is Stage.PRODUCTION

    def test_rejects_missing_metric(self):
        registry = ModelRegistry()
        candidate = registry.register(model_name="m", artifact_uri="s3://1", run_id="r1",
                                      metrics={})
        decision = auto_promote(registry, candidate, PromotionPolicy(metric="accuracy"))
        assert not decision.promote


class TestABComparison:
    def test_compare_picks_winner(self):
        registry = ModelRegistry()
        a = registry.register(model_name="m", artifact_uri="s3://a", run_id="ra",
                              metrics={"accuracy": 0.85, "latency_ms": 50.0})
        b = registry.register(model_name="m", artifact_uri="s3://b", run_id="rb",
                              metrics={"accuracy": 0.91, "latency_ms": 65.0})
        result = compare_versions(a, b, primary_metric="accuracy")
        assert result.winner == b
        assert result.deltas["accuracy"] == pytest.approx(0.06, abs=1e-6)


class TestMakeVersionFromRun:
    def test_extracts_metrics_from_run(self, tracker, registry):
        with tracker.auto_log("fraud") as run:
            tracker.log_metric(run, "accuracy", 0.91)
            tracker.log_metric(run, "f1", 0.88)
        version = make_version_from_run(
            run, model_name="fraud", artifact_uri="s3://fraud/v1", registry=registry,
        )
        assert version.metrics == {"accuracy": 0.91, "f1": 0.88}
        assert version.run_id == run.run_id
