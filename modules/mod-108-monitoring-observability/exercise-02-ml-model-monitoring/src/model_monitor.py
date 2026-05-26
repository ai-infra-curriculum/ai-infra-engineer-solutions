"""
ML Model Monitor + Auto-Rollback Coordinator

Combines the per-model metric collectors with deployment-state
tracking so the system can:

- Track the active vs. previous model version per model_id.
- Detect performance regression (accuracy / latency) crossing a
  configurable threshold.
- Trigger automatic rollback to the previous version when the
  regression persists across N consecutive evaluation windows.
- Drive an A/B-test framework where two versions ingest predictions
  simultaneously and the coordinator decides which one to promote.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional

from .metrics import (
    BiasReport,
    ClassificationMetrics,
    LatencySnapshot,
    ModelMetricsCollector,
    Prediction,
    PredictionDistribution,
    ScoreDistribution,
    SegmentFairness,
    detect_bias,
)


logger = logging.getLogger(__name__)


class ModelStage(str, Enum):
    PRIMARY = "primary"
    SHADOW = "shadow"
    AB = "ab"
    ARCHIVED = "archived"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ModelDeploymentState:
    """Active + previous version + traffic split."""

    model_id: str
    primary_version: str
    previous_version: Optional[str] = None
    candidate_version: Optional[str] = None  # for A/B
    candidate_traffic_percent: float = 0.0


@dataclass
class HealthReport:
    """Single-evaluation health snapshot."""

    model_id: str
    version: str
    classification: ClassificationMetrics
    latency: LatencySnapshot
    score_distribution: ScoreDistribution
    prediction_distribution: PredictionDistribution
    fairness: List[SegmentFairness]
    bias_reports: List[BiasReport]
    state: HealthState
    reasons: List[str] = field(default_factory=list)


@dataclass
class RollbackDecision:
    """Outcome of an evaluation cycle."""

    rolled_back: bool
    from_version: str
    to_version: Optional[str]
    reason: str
    consecutive_unhealthy_windows: int


@dataclass
class ABDecision:
    """A/B test outcome."""

    primary_version: str
    candidate_version: str
    candidate_better: bool
    promote: bool
    reason: str
    primary_metrics: ClassificationMetrics
    candidate_metrics: ClassificationMetrics


@dataclass
class MonitorConfig:
    """Tuning knobs for the model monitor."""

    min_accuracy_for_healthy: float = 0.85
    min_accuracy_for_degraded: float = 0.80
    max_p95_latency_ms_healthy: float = 200.0
    max_p95_latency_ms_degraded: float = 500.0
    rollback_after_unhealthy_windows: int = 3
    require_min_samples: int = 50
    promotion_min_improvement: float = 0.005


# -- Monitor ------------------------------------------------------------


class ModelMonitor:
    """Holds collectors per (model_id, version) and runs the decision loop."""

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self._collectors: Dict[tuple[str, str], ModelMetricsCollector] = {}
        self._deployments: Dict[str, ModelDeploymentState] = {}
        self._consecutive_unhealthy: Dict[tuple[str, str], int] = {}
        self.health_history: List[HealthReport] = []

    # -- deployment management -----------------------------------------

    def register_deployment(
        self,
        model_id: str,
        primary_version: str,
        *,
        previous_version: Optional[str] = None,
    ) -> ModelDeploymentState:
        state = ModelDeploymentState(
            model_id=model_id,
            primary_version=primary_version,
            previous_version=previous_version,
        )
        self._deployments[model_id] = state
        return state

    def start_ab_test(
        self,
        model_id: str,
        candidate_version: str,
        *,
        traffic_percent: float = 25.0,
    ) -> ModelDeploymentState:
        state = self._deployments[model_id]
        state.candidate_version = candidate_version
        state.candidate_traffic_percent = traffic_percent
        return state

    # -- ingest --------------------------------------------------------

    def record(self, prediction: Prediction) -> None:
        key = (prediction.model, prediction.model_version)
        collector = self._collectors.setdefault(key, ModelMetricsCollector())
        collector.record(prediction)

    # -- evaluation ----------------------------------------------------

    def evaluate(
        self,
        model_id: str,
        version: Optional[str] = None,
    ) -> HealthReport:
        deployment = self._deployments.get(model_id)
        version = version or (deployment.primary_version if deployment else None)
        if version is None:
            raise KeyError(f"No deployment registered for {model_id}")
        key = (model_id, version)
        collector = self._collectors.get(key)
        if collector is None:
            collector = ModelMetricsCollector()
            self._collectors[key] = collector

        metrics = collector.classification_metrics()
        latency = collector.latency_snapshot()
        scores = collector.score_distribution()
        pred_dist = collector.prediction_distribution()
        fairness = collector.segment_fairness()
        bias_reports = detect_bias(fairness, reference_segment=fairness[0].segment) if fairness else []

        state, reasons = self._classify(metrics, latency)
        report = HealthReport(
            model_id=model_id,
            version=version,
            classification=metrics,
            latency=latency,
            score_distribution=scores,
            prediction_distribution=pred_dist,
            fairness=fairness,
            bias_reports=bias_reports,
            state=state,
            reasons=reasons,
        )
        self.health_history.append(report)
        if state is HealthState.UNHEALTHY:
            self._consecutive_unhealthy[key] = self._consecutive_unhealthy.get(key, 0) + 1
        else:
            self._consecutive_unhealthy[key] = 0
        return report

    def maybe_rollback(self, model_id: str) -> RollbackDecision:
        deployment = self._deployments[model_id]
        primary_version = deployment.primary_version
        key = (model_id, primary_version)
        consecutive = self._consecutive_unhealthy.get(key, 0)
        if consecutive < self.config.rollback_after_unhealthy_windows:
            return RollbackDecision(
                rolled_back=False,
                from_version=primary_version,
                to_version=None,
                reason=f"Not yet at threshold (consecutive={consecutive})",
                consecutive_unhealthy_windows=consecutive,
            )
        if deployment.previous_version is None:
            return RollbackDecision(
                rolled_back=False,
                from_version=primary_version,
                to_version=None,
                reason="No previous version available for rollback",
                consecutive_unhealthy_windows=consecutive,
            )
        # Roll back: swap primary <-> previous, reset counter.
        previous = deployment.previous_version
        deployment.previous_version = primary_version
        deployment.primary_version = previous
        self._consecutive_unhealthy[key] = 0
        return RollbackDecision(
            rolled_back=True,
            from_version=primary_version,
            to_version=previous,
            reason=(
                f"Rolled back after {consecutive} consecutive unhealthy "
                "evaluation windows"
            ),
            consecutive_unhealthy_windows=consecutive,
        )

    # -- A/B testing ---------------------------------------------------

    def ab_evaluate(self, model_id: str) -> Optional[ABDecision]:
        deployment = self._deployments[model_id]
        if deployment.candidate_version is None:
            return None
        primary_collector = self._collectors.get((model_id, deployment.primary_version))
        candidate_collector = self._collectors.get(
            (model_id, deployment.candidate_version),
        )
        if primary_collector is None or candidate_collector is None:
            return None
        primary_metrics = primary_collector.classification_metrics()
        candidate_metrics = candidate_collector.classification_metrics()
        if primary_metrics.sample_count < self.config.require_min_samples:
            return None
        if candidate_metrics.sample_count < self.config.require_min_samples:
            return None

        delta = candidate_metrics.accuracy - primary_metrics.accuracy
        better = delta >= self.config.promotion_min_improvement
        promote = better and candidate_metrics.recall >= primary_metrics.recall * 0.95
        return ABDecision(
            primary_version=deployment.primary_version,
            candidate_version=deployment.candidate_version,
            candidate_better=better,
            promote=promote,
            reason=(
                f"Δaccuracy={delta:.4f}; "
                + ("recall regression > 5%" if better and not promote
                   else "all checks pass" if promote
                   else "Δaccuracy below threshold")
            ),
            primary_metrics=primary_metrics,
            candidate_metrics=candidate_metrics,
        )

    def promote_candidate(self, model_id: str) -> ModelDeploymentState:
        deployment = self._deployments[model_id]
        if deployment.candidate_version is None:
            raise RuntimeError("No candidate to promote")
        deployment.previous_version = deployment.primary_version
        deployment.primary_version = deployment.candidate_version
        deployment.candidate_version = None
        deployment.candidate_traffic_percent = 0.0
        return deployment

    # -- helpers -------------------------------------------------------

    def _classify(
        self,
        metrics: ClassificationMetrics,
        latency: LatencySnapshot,
    ) -> tuple[HealthState, List[str]]:
        reasons: List[str] = []
        # If we don't have enough samples for a verdict, classify HEALTHY.
        if metrics.sample_count < self.config.require_min_samples:
            return HealthState.HEALTHY, ["insufficient samples for verdict"]

        # Accuracy thresholds.
        if metrics.accuracy < self.config.min_accuracy_for_degraded:
            reasons.append(
                f"accuracy {metrics.accuracy:.4f} below degraded threshold "
                f"{self.config.min_accuracy_for_degraded}"
            )
        elif metrics.accuracy < self.config.min_accuracy_for_healthy:
            reasons.append(
                f"accuracy {metrics.accuracy:.4f} below healthy threshold "
                f"{self.config.min_accuracy_for_healthy}"
            )

        # Latency thresholds.
        if latency.samples > 0:
            if latency.p95_ms > self.config.max_p95_latency_ms_degraded:
                reasons.append(
                    f"p95 latency {latency.p95_ms:.1f}ms exceeds degraded threshold "
                    f"{self.config.max_p95_latency_ms_degraded}ms"
                )
            elif latency.p95_ms > self.config.max_p95_latency_ms_healthy:
                reasons.append(
                    f"p95 latency {latency.p95_ms:.1f}ms exceeds healthy threshold "
                    f"{self.config.max_p95_latency_ms_healthy}ms"
                )

        # Compose verdict.
        if metrics.accuracy < self.config.min_accuracy_for_degraded:
            return HealthState.UNHEALTHY, reasons
        if latency.samples > 0 and latency.p95_ms > self.config.max_p95_latency_ms_degraded:
            return HealthState.UNHEALTHY, reasons
        if reasons:
            return HealthState.DEGRADED, reasons
        return HealthState.HEALTHY, ["all thresholds met"]
