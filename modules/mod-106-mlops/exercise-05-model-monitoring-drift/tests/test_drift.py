"""Tests for the drift detector, monitor, and alerting."""

import math
import random
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from src.alerting import (
    Alert,
    AlertRouter,
    AlertSeverity,
    InMemoryAlertChannel,
    RoutingRule,
    alerts_from_report,
)
from src.drift_detector import (
    DriftDetector,
    DriftSeverity,
    DriftTest,
    FeatureSpec,
    chi_square_test,
    concept_drift_from_accuracy,
    detect_concept_drift_from_predictions,
    ks_statistic,
    ks_test,
    population_stability_index,
    psi_test,
)
from src.monitor import (
    ModelMonitor,
    PerformanceTracker,
    PredictionRecord,
    RetrainingPolicy,
    RetrainingReason,
)


def _normal(n: int, mean: float, std: float, *, seed: int) -> List[float]:
    rng = random.Random(seed)
    return [rng.gauss(mean, std) for _ in range(n)]


class TestKSTest:
    def test_identical_distributions(self):
        ref = _normal(500, 0.0, 1.0, seed=1)
        live = _normal(500, 0.0, 1.0, seed=2)
        result = ks_test("x", ref, live)
        # Statistic is small; not necessarily 0, but typically below 0.1.
        assert result.statistic < 0.15

    def test_shifted_distribution_detected(self):
        ref = _normal(500, 0.0, 1.0, seed=1)
        live = _normal(500, 1.5, 1.0, seed=2)
        result = ks_test("x", ref, live)
        assert result.detected
        assert result.severity is DriftSeverity.MAJOR

    def test_empty_returns_no_drift(self):
        result = ks_test("x", [], [1.0, 2.0, 3.0])
        assert not result.detected
        assert result.severity is DriftSeverity.NONE


class TestPSI:
    def test_identical_distributions_near_zero(self):
        ref = _normal(500, 0.0, 1.0, seed=1)
        live = _normal(500, 0.0, 1.0, seed=2)
        psi, breakdown = population_stability_index(ref, live)
        assert psi < 0.1
        assert len(breakdown) == 10

    def test_shifted_distribution_high_psi(self):
        ref = _normal(500, 0.0, 1.0, seed=1)
        live = _normal(500, 1.0, 1.0, seed=2)
        psi, _ = population_stability_index(ref, live)
        assert psi > 0.25

    def test_psi_test_severity_thresholds(self):
        ref = _normal(500, 0.0, 1.0, seed=1)
        live = _normal(500, 1.0, 1.0, seed=2)
        result = psi_test("x", ref, live, minor_threshold=0.1, moderate_threshold=0.25)
        assert result.detected
        assert result.severity in {DriftSeverity.MODERATE, DriftSeverity.MAJOR}


class TestChiSquare:
    def test_same_distribution(self):
        ref = ["a"] * 100 + ["b"] * 100
        live = ["a"] * 100 + ["b"] * 100
        result = chi_square_test("cat", ref, live)
        assert not result.detected

    def test_different_distribution(self):
        ref = ["a"] * 200
        live = ["b"] * 200
        result = chi_square_test("cat", ref, live)
        assert result.detected
        assert result.severity is DriftSeverity.MODERATE

    def test_new_category(self):
        ref = ["a"] * 200 + ["b"] * 200
        live = ["a"] * 200 + ["c"] * 200  # 'c' is new
        result = chi_square_test("cat", ref, live)
        assert result.detected


class TestDriftDetectorAggregate:
    def test_runs_all_configured_tests(self):
        ref = {
            "num": _normal(200, 0.0, 1.0, seed=1),
            "cat": ["a"] * 100 + ["b"] * 100,
        }
        live = {
            "num": _normal(200, 1.5, 1.0, seed=2),
            "cat": ["a"] * 50 + ["b"] * 150,
        }
        detector = DriftDetector([
            FeatureSpec("num", "numeric", DriftTest.KS),
            FeatureSpec("cat", "categorical", DriftTest.CHI_SQUARE),
        ])
        results = detector.detect(ref, live)
        assert len(results) == 2
        # Both should detect drift.
        assert all(r.detected for r in results)


class TestConceptDrift:
    def test_no_drift_when_accuracy_matches(self):
        result = concept_drift_from_accuracy(0.95, 0.95)
        assert not result.detected

    def test_minor_drop(self):
        result = concept_drift_from_accuracy(0.95, 0.92)
        assert result.detected
        assert result.severity is DriftSeverity.MINOR

    def test_major_drop(self):
        result = concept_drift_from_accuracy(0.95, 0.80)
        assert result.detected
        assert result.severity is DriftSeverity.MAJOR

    def test_from_predictions(self):
        ref = [True] * 95 + [False] * 5
        live = [True] * 80 + [False] * 20
        result = detect_concept_drift_from_predictions(ref, live)
        assert result.detected
        assert result.live_accuracy == 0.8


class TestPerformanceTracker:
    def test_metrics_for_clean_predictions(self):
        tracker = PerformanceTracker()
        for _ in range(100):
            tracker.record(PredictionRecord(prediction=1, label=1))
        snapshot = tracker.snapshot()
        assert snapshot.accuracy == 1.0
        assert snapshot.precision == 1.0
        assert snapshot.recall == 1.0
        assert snapshot.f1 == 1.0

    def test_metrics_mixed(self):
        tracker = PerformanceTracker()
        # 80 TP, 10 FP, 5 FN, 5 TN.
        for _ in range(80):
            tracker.record(PredictionRecord(prediction=1, label=1))
        for _ in range(10):
            tracker.record(PredictionRecord(prediction=1, label=0))
        for _ in range(5):
            tracker.record(PredictionRecord(prediction=0, label=1))
        for _ in range(5):
            tracker.record(PredictionRecord(prediction=0, label=0))
        snapshot = tracker.snapshot()
        assert snapshot.accuracy == pytest.approx(0.85, abs=0.01)
        assert snapshot.precision == pytest.approx(0.8889, abs=0.01)
        assert snapshot.recall == pytest.approx(0.9412, abs=0.01)

    def test_window_caps_at_size(self):
        tracker = PerformanceTracker(window_size=10)
        for _ in range(50):
            tracker.record(PredictionRecord(prediction=1, label=1))
        assert tracker.snapshot().sample_count == 10


class TestModelMonitor:
    def _setup(self, *, drifted: bool, accuracy: float) -> ModelMonitor:
        ref = {
            "amount": _normal(200, 0.0, 1.0, seed=1),
            "category": ["a"] * 100 + ["b"] * 100,
        }
        feature_specs = [
            FeatureSpec("amount", "numeric", DriftTest.KS),
            FeatureSpec("category", "categorical", DriftTest.CHI_SQUARE),
        ]
        monitor = ModelMonitor(
            feature_specs=feature_specs,
            reference_data=ref,
            reference_accuracy=0.95,
            retraining_policy=RetrainingPolicy(
                min_accuracy_drop_to_retrain=0.05,
                drift_severity_to_retrain=DriftSeverity.MODERATE,
            ),
        )
        for i in range(200):
            correct = i / 200 < accuracy
            label = 1 if i % 3 == 0 else 0
            prediction = label if correct else (1 - label)
            monitor.observe_prediction(PredictionRecord(prediction=prediction, label=label))
        return monitor

    def test_no_drift_no_retraining(self):
        monitor = self._setup(drifted=False, accuracy=0.95)
        live = {
            "amount": _normal(200, 0.0, 1.0, seed=2),
            "category": ["a"] * 100 + ["b"] * 100,
        }
        report = monitor.evaluate(live)
        assert not report.retraining_required
        assert report.retraining_reason is RetrainingReason.NONE

    def test_data_drift_triggers_retraining(self):
        monitor = self._setup(drifted=True, accuracy=0.95)
        live = {
            "amount": _normal(200, 2.0, 1.0, seed=2),  # major shift
            "category": ["a"] * 100 + ["b"] * 100,
        }
        report = monitor.evaluate(live)
        assert report.retraining_required
        assert report.retraining_reason is RetrainingReason.DATA_DRIFT

    def test_concept_drift_triggers_retraining(self):
        monitor = self._setup(drifted=False, accuracy=0.80)  # 15pp accuracy drop
        live = {
            "amount": _normal(200, 0.0, 1.0, seed=2),
            "category": ["a"] * 100 + ["b"] * 100,
        }
        report = monitor.evaluate(live)
        assert report.retraining_required
        # Either concept_drift OR performance trigger is acceptable here.
        assert report.retraining_reason in {
            RetrainingReason.CONCEPT_DRIFT, RetrainingReason.PERFORMANCE,
        }

    def test_performance_floor_triggers_retraining(self):
        monitor = self._setup(drifted=False, accuracy=0.70)
        live = {
            "amount": _normal(200, 0.0, 1.0, seed=2),
            "category": ["a"] * 100 + ["b"] * 100,
        }
        report = monitor.evaluate(live)
        assert report.retraining_required
        assert report.retraining_reason is RetrainingReason.PERFORMANCE

    def test_update_reference_resets_window(self):
        monitor = self._setup(drifted=False, accuracy=0.95)
        new_ref = {"amount": _normal(100, 0.0, 1.0, seed=99), "category": ["a"] * 100}
        monitor.update_reference(new_ref)
        assert monitor.tracker.snapshot().sample_count == 0

    def test_history_grows(self):
        monitor = self._setup(drifted=False, accuracy=0.95)
        live = {
            "amount": _normal(100, 0.0, 1.0, seed=10),
            "category": ["a"] * 50 + ["b"] * 50,
        }
        for _ in range(3):
            monitor.evaluate(live)
        assert len(monitor.history) == 3


class TestAlerting:
    def _ts(self) -> datetime:
        return datetime.now(timezone.utc)

    def test_router_routes_above_threshold(self):
        slack = InMemoryAlertChannel("slack")
        pager = InMemoryAlertChannel("pagerduty")
        router = AlertRouter([
            RoutingRule(AlertSeverity.WARNING, slack),
            RoutingRule(AlertSeverity.CRITICAL, pager),
        ])
        sent = router.emit(Alert(
            title="t", severity=AlertSeverity.WARNING, body="b",
            timestamp=self._ts(),
        ))
        assert "slack" in sent
        assert "pagerduty" not in sent

    def test_router_cooldown_dedupes(self):
        slack = InMemoryAlertChannel("slack")
        router = AlertRouter(
            [RoutingRule(AlertSeverity.WARNING, slack)],
            cooldown=timedelta(minutes=5),
        )
        a = Alert(title="t", severity=AlertSeverity.WARNING, body="b", timestamp=self._ts())
        router.emit(a)
        router.emit(a)  # duplicate within cooldown
        assert len(slack.alerts) == 1

    def test_alerts_from_report_critical_drift(self):
        # Construct a report-like object with major drift.
        from src.monitor import (
            ModelMonitor as _MM, PredictionRecord, RetrainingPolicy,
            MonitorReport, PerformanceSnapshot,
        )
        from src.drift_detector import DriftResult
        report = MonitorReport(
            timestamp=self._ts(),
            drift_results=[
                DriftResult(
                    feature="amount", test=DriftTest.KS, statistic=0.5,
                    p_value=0.0001, threshold=0.05, detected=True,
                    severity=DriftSeverity.MAJOR,
                    reference_size=100, live_size=100,
                ),
            ],
            concept_drift=None,
            performance=PerformanceSnapshot(0.9, 0.9, 0.9, 0.9, 100),
            retraining_reason=RetrainingReason.DATA_DRIFT,
            retraining_required=True,
        )
        alerts = alerts_from_report(report)
        # Should fire: major data drift (critical) + retraining triggered (info).
        severities = [a.severity for a in alerts]
        assert AlertSeverity.CRITICAL in severities
        assert AlertSeverity.INFO in severities
