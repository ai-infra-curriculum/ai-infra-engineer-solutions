"""
Model Monitor

Combines the drift detector with rolling performance tracking and a
retraining trigger. Records per-feature drift findings, model accuracy/
precision/recall over time, and emits MonitorReport snapshots the
alerting layer consumes.

The monitor keeps a sliding window of live predictions + ground truth
so it can compute concept-drift signals; the window size and the
retraining policy are configurable.
"""

from __future__ import annotations

import logging
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Deque, Dict, List, Optional, Tuple

from .drift_detector import (
    ConceptDriftResult,
    DriftDetector,
    DriftResult,
    DriftSeverity,
    FeatureSpec,
    detect_concept_drift_from_predictions,
)


logger = logging.getLogger(__name__)


class RetrainingReason(str, Enum):
    NONE = "none"
    DATA_DRIFT = "data_drift"
    CONCEPT_DRIFT = "concept_drift"
    PERFORMANCE = "performance"


@dataclass
class PredictionRecord:
    """One labeled prediction the monitor uses for concept-drift tracking."""

    prediction: int
    label: int
    score: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PerformanceSnapshot:
    """Rolling-window classification metrics."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    sample_count: int


@dataclass
class MonitorReport:
    """Output of one monitoring cycle."""

    timestamp: datetime
    drift_results: List[DriftResult]
    concept_drift: Optional[ConceptDriftResult]
    performance: PerformanceSnapshot
    retraining_reason: RetrainingReason
    retraining_required: bool

    @property
    def drifted_features(self) -> List[str]:
        return [r.feature for r in self.drift_results if r.detected]


@dataclass
class RetrainingPolicy:
    """Declarative trigger for retraining."""

    min_accuracy_drop_to_retrain: float = 0.05
    drift_severity_to_retrain: DriftSeverity = DriftSeverity.MODERATE
    min_drifted_features: int = 1
    min_accuracy_floor: Optional[float] = 0.85


class PerformanceTracker:
    """Rolling-window classification metrics."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._records: Deque[PredictionRecord] = deque(maxlen=window_size)

    def record(self, record: PredictionRecord) -> None:
        self._records.append(record)

    def snapshot(self) -> PerformanceSnapshot:
        if not self._records:
            return PerformanceSnapshot(0.0, 0.0, 0.0, 0.0, 0)
        tp = fp = tn = fn = 0
        for r in self._records:
            if r.label == 1 and r.prediction == 1:
                tp += 1
            elif r.label == 0 and r.prediction == 1:
                fp += 1
            elif r.label == 1 and r.prediction == 0:
                fn += 1
            else:
                tn += 1
        total = tp + fp + tn + fn
        accuracy = (tp + tn) / total if total else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) else 0.0
        )
        return PerformanceSnapshot(
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            sample_count=total,
        )


class ModelMonitor:
    """Closed-loop drift + performance monitor for a single model."""

    def __init__(
        self,
        feature_specs: List[FeatureSpec],
        *,
        reference_data: Dict[str, List],
        reference_accuracy: float = 0.95,
        performance_window: int = 1000,
        retraining_policy: Optional[RetrainingPolicy] = None,
    ):
        self.detector = DriftDetector(feature_specs)
        self.reference = dict(reference_data)
        self.reference_accuracy = reference_accuracy
        self.tracker = PerformanceTracker(window_size=performance_window)
        self.policy = retraining_policy or RetrainingPolicy()
        self.history: List[MonitorReport] = []

    def observe_prediction(self, record: PredictionRecord) -> None:
        self.tracker.record(record)

    def update_reference(self, new_reference: Dict[str, List]) -> None:
        """Replace reference distributions after a retraining cycle."""
        self.reference = dict(new_reference)
        # Reset rolling window so post-retraining metrics aren't polluted.
        self.tracker = PerformanceTracker(window_size=self.tracker.window_size)

    def evaluate(self, live_data: Dict[str, List]) -> MonitorReport:
        drift_results = self.detector.detect(self.reference, live_data)
        performance = self.tracker.snapshot()
        concept = None
        if performance.sample_count > 0:
            concept = detect_concept_drift_from_predictions(
                reference_correct=[True] * int(self.reference_accuracy * 100)
                + [False] * (100 - int(self.reference_accuracy * 100)),
                live_correct=[True] * int(performance.accuracy * performance.sample_count)
                + [False] * (performance.sample_count - int(performance.accuracy * performance.sample_count)),
            )
        reason = self._evaluate_retraining(drift_results, concept, performance)
        report = MonitorReport(
            timestamp=datetime.now(timezone.utc),
            drift_results=drift_results,
            concept_drift=concept,
            performance=performance,
            retraining_reason=reason,
            retraining_required=reason is not RetrainingReason.NONE,
        )
        self.history.append(report)
        return report

    def _evaluate_retraining(
        self,
        drift_results: List[DriftResult],
        concept: Optional[ConceptDriftResult],
        performance: PerformanceSnapshot,
    ) -> RetrainingReason:
        # Hard performance floor: retrain if accuracy collapses.
        if self.policy.min_accuracy_floor is not None and performance.sample_count > 0:
            if performance.accuracy < self.policy.min_accuracy_floor:
                return RetrainingReason.PERFORMANCE
        if concept and concept.detected:
            drop = self.reference_accuracy - performance.accuracy
            if drop >= self.policy.min_accuracy_drop_to_retrain:
                return RetrainingReason.CONCEPT_DRIFT
        # Data drift: count features at or above the policy severity.
        severity_order = {
            DriftSeverity.NONE: 0,
            DriftSeverity.MINOR: 1,
            DriftSeverity.MODERATE: 2,
            DriftSeverity.MAJOR: 3,
        }
        threshold = severity_order[self.policy.drift_severity_to_retrain]
        drifted = [
            r for r in drift_results
            if severity_order[r.severity] >= threshold
        ]
        if len(drifted) >= self.policy.min_drifted_features:
            return RetrainingReason.DATA_DRIFT
        return RetrainingReason.NONE
