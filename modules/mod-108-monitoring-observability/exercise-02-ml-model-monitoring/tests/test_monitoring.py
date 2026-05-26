"""Tests for the ML model monitoring system."""

import pytest

from src.metrics import (
    ClassificationMetrics,
    ModelMetricsCollector,
    Prediction,
    detect_bias,
)
from src.model_monitor import (
    HealthState,
    ModelMonitor,
    MonitorConfig,
)


def _pred(*, model="m", version="v1", prediction=1, label=1, latency_ms=50.0,
          segment=None, score=0.5) -> Prediction:
    return Prediction(
        model=model, model_version=version,
        prediction=prediction, score=score,
        label=label, latency_ms=latency_ms, segment=segment,
    )


class TestClassificationMetrics:
    def test_perfect_predictions(self):
        preds = [_pred(prediction=1, label=1) for _ in range(50)]
        preds += [_pred(prediction=0, label=0) for _ in range(50)]
        metrics = ClassificationMetrics.from_predictions(preds)
        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0

    def test_zero_predictions_safe(self):
        metrics = ClassificationMetrics.from_predictions([])
        assert metrics.sample_count == 0
        assert metrics.accuracy == 0.0

    def test_skipped_unlabeled(self):
        preds = [_pred(prediction=1, label=None) for _ in range(5)]
        preds += [_pred(prediction=1, label=1) for _ in range(5)]
        metrics = ClassificationMetrics.from_predictions(preds)
        # Unlabeled predictions are excluded from the confusion matrix.
        assert metrics.sample_count == 5
        assert metrics.accuracy == 1.0


class TestModelMetricsCollector:
    def test_latency_snapshot(self):
        c = ModelMetricsCollector()
        for ms in [50, 60, 100, 120, 200, 250, 300, 500, 800]:
            c.record(_pred(latency_ms=float(ms)))
        snap = c.latency_snapshot()
        assert snap.samples == 9
        assert snap.p50_ms > 0
        assert snap.p95_ms >= snap.p50_ms
        assert snap.p99_ms >= snap.p95_ms

    def test_window_caps(self):
        c = ModelMetricsCollector(window_size=10)
        for _ in range(50):
            c.record(_pred())
        assert len(c) == 10

    def test_score_distribution(self):
        c = ModelMetricsCollector()
        for s in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            c.record(_pred(score=s))
        sd = c.score_distribution()
        assert sd.min_score == pytest.approx(0.1)
        assert sd.max_score == pytest.approx(0.9)
        assert sd.p50 == pytest.approx(0.5, abs=0.05)

    def test_prediction_distribution_baseline_drift(self):
        c = ModelMetricsCollector(baseline_positive_rate=0.3)
        for _ in range(80):
            c.record(_pred(prediction=1))
        for _ in range(20):
            c.record(_pred(prediction=0))
        dist = c.prediction_distribution()
        assert dist.counts == {1: 80, 0: 20}
        assert dist.positive_rate == 0.8
        # Drift = (0.8 - 0.3) / 0.3 ≈ +166%.
        assert dist.drift_from_baseline_percent > 100.0

    def test_segment_fairness(self):
        c = ModelMetricsCollector()
        for _ in range(100):
            c.record(_pred(prediction=1, label=1, segment="us"))
        for _ in range(100):
            c.record(_pred(prediction=0, label=1, segment="eu"))
        results = c.segment_fairness()
        segments = {s.segment: s for s in results}
        # us model is perfectly accurate.
        assert segments["us"].accuracy == 1.0
        # eu model is perfectly wrong.
        assert segments["eu"].accuracy == 0.0


class TestBiasDetection:
    def test_disparate_impact_flagged(self):
        c = ModelMetricsCollector()
        # Reference group ('us'): 50% positive rate.
        for i in range(100):
            c.record(_pred(prediction=(1 if i < 50 else 0),
                            label=(1 if i < 50 else 0), segment="us"))
        # Other group ('eu'): 10% positive rate — 5x lower.
        for i in range(100):
            c.record(_pred(prediction=(1 if i < 10 else 0),
                            label=(1 if i < 50 else 0), segment="eu"))
        fairness = c.segment_fairness()
        bias = detect_bias(fairness, reference_segment="us")
        assert bias
        eu = next(b for b in bias if b.other_segment == "eu")
        # ratio = 0.1/0.5 = 0.2 → under 0.8 threshold → disparate impact.
        assert eu.disparate_impact
        # Accuracy gap should also breach the default 0.05 threshold.
        assert eu.accuracy_gap_breach

    def test_no_bias_within_thresholds(self):
        c = ModelMetricsCollector()
        for i in range(100):
            for segment in ("us", "eu"):
                c.record(_pred(prediction=(1 if i < 50 else 0),
                                label=(1 if i < 50 else 0),
                                segment=segment))
        fairness = c.segment_fairness()
        bias = detect_bias(fairness, reference_segment="us")
        assert all(not b.disparate_impact for b in bias)


class TestModelMonitor:
    def _setup(
        self,
        *,
        accuracy: float = 0.95,
        latency_p95: float = 100.0,
        samples: int = 200,
        config: MonitorConfig = None,
    ) -> ModelMonitor:
        monitor = ModelMonitor(config=config or MonitorConfig(
            min_accuracy_for_healthy=0.90,
            min_accuracy_for_degraded=0.80,
            max_p95_latency_ms_healthy=200.0,
            max_p95_latency_ms_degraded=500.0,
            rollback_after_unhealthy_windows=2,
            require_min_samples=50,
        ))
        monitor.register_deployment(
            model_id="m",
            primary_version="v1",
            previous_version="v0",
        )
        for i in range(samples):
            correct = i / samples < accuracy
            label = 1 if i % 3 == 0 else 0
            prediction = label if correct else 1 - label
            latency = latency_p95 * (0.4 if i % 10 != 0 else 1.5)
            monitor.record(Prediction(
                model="m", model_version="v1",
                prediction=prediction, score=0.5, label=label,
                latency_ms=latency, segment="us",
            ))
        return monitor

    def test_healthy_model_passes(self):
        monitor = self._setup(accuracy=0.95, latency_p95=100.0)
        report = monitor.evaluate("m")
        assert report.state is HealthState.HEALTHY

    def test_degraded_state_for_lower_accuracy(self):
        monitor = self._setup(accuracy=0.85, latency_p95=100.0)
        report = monitor.evaluate("m")
        assert report.state is HealthState.DEGRADED

    def test_unhealthy_state_below_floor(self):
        monitor = self._setup(accuracy=0.70, latency_p95=100.0)
        report = monitor.evaluate("m")
        assert report.state is HealthState.UNHEALTHY

    def test_unhealthy_state_high_latency(self):
        monitor = self._setup(accuracy=0.95, latency_p95=800.0)
        report = monitor.evaluate("m")
        assert report.state is HealthState.UNHEALTHY

    def test_rollback_triggers_after_threshold(self):
        monitor = self._setup(accuracy=0.70, latency_p95=100.0)
        monitor.evaluate("m")
        monitor.evaluate("m")
        decision = monitor.maybe_rollback("m")
        assert decision.rolled_back
        assert decision.from_version == "v1"
        assert decision.to_version == "v0"

    def test_no_rollback_below_threshold(self):
        monitor = self._setup(accuracy=0.70, latency_p95=100.0)
        monitor.evaluate("m")
        decision = monitor.maybe_rollback("m")
        assert not decision.rolled_back

    def test_no_rollback_when_no_previous(self):
        monitor = ModelMonitor(MonitorConfig(
            min_accuracy_for_degraded=0.80,
            rollback_after_unhealthy_windows=1,
            require_min_samples=10,
        ))
        monitor.register_deployment("m", primary_version="v1")
        for i in range(100):
            monitor.record(Prediction(
                model="m", model_version="v1",
                prediction=0, score=0.5, label=1, latency_ms=50.0,
            ))
        monitor.evaluate("m")
        decision = monitor.maybe_rollback("m")
        assert not decision.rolled_back
        assert "No previous version" in decision.reason

    def test_rollback_resets_counter(self):
        monitor = self._setup(accuracy=0.70, latency_p95=100.0)
        monitor.evaluate("m")
        monitor.evaluate("m")
        monitor.maybe_rollback("m")
        # After rollback, primary is now v0; subsequent evaluations should
        # not immediately trigger another rollback.
        decision = monitor.maybe_rollback("m")
        assert not decision.rolled_back


class TestABTesting:
    def test_promotion_on_clear_improvement(self):
        monitor = ModelMonitor(MonitorConfig(
            require_min_samples=50, promotion_min_improvement=0.005,
        ))
        monitor.register_deployment("m", primary_version="v1", previous_version="v0")
        monitor.start_ab_test("m", candidate_version="v2", traffic_percent=25.0)
        # Primary: 85% accuracy.
        for i in range(200):
            label = 1 if i % 2 == 0 else 0
            correct = i < 170
            monitor.record(Prediction(
                model="m", model_version="v1",
                prediction=label if correct else 1 - label,
                score=0.5, label=label, latency_ms=50.0,
            ))
        # Candidate: 95% accuracy.
        for i in range(200):
            label = 1 if i % 2 == 0 else 0
            correct = i < 190
            monitor.record(Prediction(
                model="m", model_version="v2",
                prediction=label if correct else 1 - label,
                score=0.5, label=label, latency_ms=45.0,
            ))
        decision = monitor.ab_evaluate("m")
        assert decision is not None
        assert decision.promote
        state = monitor.promote_candidate("m")
        assert state.primary_version == "v2"
        assert state.previous_version == "v1"

    def test_no_promotion_if_below_threshold(self):
        monitor = ModelMonitor(MonitorConfig(
            require_min_samples=50, promotion_min_improvement=0.05,
        ))
        monitor.register_deployment("m", primary_version="v1", previous_version="v0")
        monitor.start_ab_test("m", candidate_version="v2")
        for i in range(200):
            label = 1 if i % 2 == 0 else 0
            correct = i < 180
            for v in ("v1", "v2"):
                monitor.record(Prediction(
                    model="m", model_version=v,
                    prediction=label if correct else 1 - label,
                    score=0.5, label=label, latency_ms=50.0,
                ))
        decision = monitor.ab_evaluate("m")
        assert decision is not None
        assert not decision.promote

    def test_no_ab_decision_without_candidate(self):
        monitor = ModelMonitor()
        monitor.register_deployment("m", primary_version="v1")
        assert monitor.ab_evaluate("m") is None

    def test_promote_candidate_requires_one(self):
        monitor = ModelMonitor()
        monitor.register_deployment("m", primary_version="v1")
        with pytest.raises(RuntimeError):
            monitor.promote_candidate("m")
