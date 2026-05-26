"""
ML-Specific Production Metrics

Per-model online classification metrics, prediction-distribution
tracking, and per-segment fairness checks. Complements the more
general drift detector in mod-106/ex-05 with model-serving-time
metrics: rolling latency, throughput, prediction-class distribution,
per-segment accuracy.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Deque, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Prediction:
    """One model prediction + (optional) ground-truth label."""

    model: str
    model_version: str
    prediction: int
    score: float
    label: Optional[int] = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    segment: Optional[str] = None  # e.g., region, customer-tier
    feature_hash: Optional[str] = None


@dataclass
class ClassificationMetrics:
    """Standard confusion-matrix metrics."""

    sample_count: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    @classmethod
    def from_predictions(cls, predictions: Iterable[Prediction]) -> "ClassificationMetrics":
        tp = fp = tn = fn = 0
        for p in predictions:
            if p.label is None:
                continue
            if p.label == 1 and p.prediction == 1:
                tp += 1
            elif p.label == 0 and p.prediction == 1:
                fp += 1
            elif p.label == 1 and p.prediction == 0:
                fn += 1
            else:
                tn += 1
        total = tp + fp + tn + fn
        accuracy = (tp + tn) / total if total else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return cls(
            sample_count=total,
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            true_positive=tp, false_positive=fp,
            true_negative=tn, false_negative=fn,
        )


@dataclass
class ScoreDistribution:
    """Score distribution statistics."""

    mean: float
    std_dev: float
    min_score: float
    max_score: float
    p10: float
    p50: float
    p90: float
    p99: float

    @classmethod
    def from_predictions(cls, predictions: Iterable[Prediction]) -> "ScoreDistribution":
        scores = [p.score for p in predictions]
        if not scores:
            return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        sorted_scores = sorted(scores)
        return cls(
            mean=round(statistics.mean(scores), 4),
            std_dev=round(statistics.pstdev(scores) if len(scores) > 1 else 0.0, 4),
            min_score=round(sorted_scores[0], 4),
            max_score=round(sorted_scores[-1], 4),
            p10=round(_percentile(sorted_scores, 10), 4),
            p50=round(_percentile(sorted_scores, 50), 4),
            p90=round(_percentile(sorted_scores, 90), 4),
            p99=round(_percentile(sorted_scores, 99), 4),
        )


@dataclass
class LatencySnapshot:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    samples: int


@dataclass
class PredictionDistribution:
    """Per-class output distribution for the recent prediction window."""

    counts: Dict[int, int]
    total: int
    positive_rate: float
    drift_from_baseline_percent: Optional[float]


@dataclass
class SegmentFairness:
    """Per-segment accuracy + positive rate."""

    segment: str
    accuracy: float
    positive_rate: float
    sample_count: int


# -- Window-based metrics collector ------------------------------------


class ModelMetricsCollector:
    """Streams Predictions into rolling-window metrics + fairness probes."""

    def __init__(
        self,
        *,
        window_size: int = 5000,
        baseline_positive_rate: Optional[float] = None,
    ):
        self.window_size = window_size
        self.baseline_positive_rate = baseline_positive_rate
        self._predictions: Deque[Prediction] = deque(maxlen=window_size)

    def record(self, prediction: Prediction) -> None:
        self._predictions.append(prediction)

    def __len__(self) -> int:
        return len(self._predictions)

    def latency_snapshot(self) -> LatencySnapshot:
        latencies = [p.latency_ms for p in self._predictions if p.latency_ms > 0]
        if not latencies:
            return LatencySnapshot(0.0, 0.0, 0.0, 0.0, 0)
        sorted_l = sorted(latencies)
        return LatencySnapshot(
            p50_ms=round(_percentile(sorted_l, 50), 2),
            p95_ms=round(_percentile(sorted_l, 95), 2),
            p99_ms=round(_percentile(sorted_l, 99), 2),
            avg_ms=round(statistics.mean(latencies), 2),
            samples=len(latencies),
        )

    def classification_metrics(self) -> ClassificationMetrics:
        return ClassificationMetrics.from_predictions(self._predictions)

    def score_distribution(self) -> ScoreDistribution:
        return ScoreDistribution.from_predictions(self._predictions)

    def prediction_distribution(self) -> PredictionDistribution:
        counts: Dict[int, int] = {}
        for p in self._predictions:
            counts[p.prediction] = counts.get(p.prediction, 0) + 1
        total = sum(counts.values())
        positive_rate = counts.get(1, 0) / total if total else 0.0
        drift = None
        if self.baseline_positive_rate is not None and self.baseline_positive_rate > 0:
            drift = round(
                (positive_rate - self.baseline_positive_rate)
                / self.baseline_positive_rate * 100.0,
                2,
            )
        return PredictionDistribution(
            counts=dict(counts),
            total=total,
            positive_rate=round(positive_rate, 4),
            drift_from_baseline_percent=drift,
        )

    def segment_fairness(self) -> List[SegmentFairness]:
        """Compute accuracy + positive rate per segment."""
        by_segment: Dict[str, List[Prediction]] = {}
        for p in self._predictions:
            if p.segment is None:
                continue
            by_segment.setdefault(p.segment, []).append(p)
        results: List[SegmentFairness] = []
        for segment, preds in by_segment.items():
            metrics = ClassificationMetrics.from_predictions(preds)
            positive_count = sum(1 for p in preds if p.prediction == 1)
            results.append(SegmentFairness(
                segment=segment,
                accuracy=metrics.accuracy,
                positive_rate=round(positive_count / len(preds), 4) if preds else 0.0,
                sample_count=len(preds),
            ))
        results.sort(key=lambda s: -s.sample_count)
        return results

    def predictions(self) -> List[Prediction]:
        return list(self._predictions)


# -- Bias detection -----------------------------------------------------


@dataclass
class BiasReport:
    """Disparate-impact + accuracy-gap report."""

    reference_segment: str
    other_segment: str
    positive_rate_ratio: float  # P(positive | other) / P(positive | reference)
    accuracy_gap: float  # |accuracy_other - accuracy_reference|
    disparate_impact: bool  # True if positive_rate_ratio < 0.8 or > 1.25
    accuracy_gap_breach: bool  # True if accuracy gap > threshold
    threshold: float


def detect_bias(
    fairness: List[SegmentFairness],
    *,
    reference_segment: str,
    accuracy_gap_threshold: float = 0.05,
) -> List[BiasReport]:
    """Compare each segment against the reference; flag disparate impact."""
    ref = next((f for f in fairness if f.segment == reference_segment), None)
    if ref is None:
        return []
    reports: List[BiasReport] = []
    for segment in fairness:
        if segment.segment == reference_segment:
            continue
        ratio = (
            segment.positive_rate / ref.positive_rate
            if ref.positive_rate > 0 else 0.0
        )
        gap = abs(segment.accuracy - ref.accuracy)
        reports.append(BiasReport(
            reference_segment=reference_segment,
            other_segment=segment.segment,
            positive_rate_ratio=round(ratio, 4),
            accuracy_gap=round(gap, 4),
            disparate_impact=(ratio < 0.8 or ratio > 1.25) if ref.positive_rate > 0 else False,
            accuracy_gap_breach=gap > accuracy_gap_threshold,
            threshold=accuracy_gap_threshold,
        ))
    return reports


# -- helpers ------------------------------------------------------------


def _percentile(sorted_values: List[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return sorted_values[int(k)]
    return sorted_values[lower] * (upper - k) + sorted_values[upper] * (k - lower)
