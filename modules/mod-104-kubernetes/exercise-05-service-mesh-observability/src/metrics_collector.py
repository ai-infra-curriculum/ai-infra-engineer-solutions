"""
Service-Mesh Metrics Collector

Computes the golden signals (latency, traffic, errors, saturation),
service-to-service dependency edges, SLO/error-budget status, and
canary rollout health from a stream of completed request observations
(or directly from a TraceExporter's captured spans).

Designed to plug into the Tracer in `tracer.py`: pass an InMemoryExporter
to record_request() and the collector reads everything it needs from
the recorded spans.
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Deque, Dict, Iterable, List, Optional, Tuple

from .tracer import InMemoryExporter, Span, SpanStatus, TraceTree, build_trace_tree


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestObservation:
    """One end-to-end request outcome."""

    service: str
    route: str
    duration_ms: float
    status_code: int
    timestamp: datetime
    upstream: Optional[str] = None  # caller service, if known

    @property
    def is_error(self) -> bool:
        return self.status_code >= 500


@dataclass
class GoldenSignals:
    """Golden-signal snapshot for a single service."""

    service: str
    request_rate_per_second: float
    error_rate_percent: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    saturation_percent: float  # 0..100 (queue+utilization proxy)
    sample_count: int


@dataclass
class ServiceEdge:
    """One directed call between two services."""

    upstream: str
    downstream: str
    request_count: int = 0
    error_count: int = 0
    p95_latency_ms: float = 0.0

    @property
    def error_rate_percent(self) -> float:
        if self.request_count == 0:
            return 0.0
        return (self.error_count / self.request_count) * 100.0


@dataclass(frozen=True)
class SLO:
    """Declarative SLO target."""

    name: str
    service: str
    availability_target: float = 0.999  # 99.9%
    latency_target_ms: float = 100.0
    latency_target_percentile: float = 95.0
    window_days: int = 30


@dataclass
class SLOStatus:
    """SLO compliance + remaining error budget."""

    slo: SLO
    observed_availability: float
    observed_p95_ms: float
    error_budget_total: float  # fraction (e.g., 0.001 for 99.9% SLO)
    error_budget_consumed: float  # 0..1 of total budget consumed
    burn_rate: float  # >1 = consuming faster than allowed
    breach: bool


@dataclass(frozen=True)
class CanaryRollout:
    """Configuration for a canary rollout step."""

    service: str
    baseline_version: str
    candidate_version: str
    candidate_weight_percent: float


@dataclass
class CanaryDecision:
    """Outcome of comparing canary against baseline."""

    rollout: CanaryRollout
    baseline_error_rate: float
    candidate_error_rate: float
    baseline_p95: float
    candidate_p95: float
    promote: bool
    rollback: bool
    rationale: str


class GoldenSignalsCollector:
    """Rolling-window collector for per-service golden signals."""

    def __init__(self, *, window_seconds: int = 60):
        self.window = timedelta(seconds=window_seconds)
        self._observations: Dict[str, Deque[RequestObservation]] = defaultdict(deque)
        # Saturation = average concurrency. Captured by add_concurrency_sample.
        self._concurrency: Dict[str, Deque[Tuple[datetime, float]]] = defaultdict(deque)

    def record(self, observation: RequestObservation) -> None:
        bucket = self._observations[observation.service]
        bucket.append(observation)
        self._trim(observation.service, observation.timestamp)

    def add_concurrency_sample(self, service: str, value: float, *, now: Optional[datetime] = None) -> None:
        bucket = self._concurrency[service]
        bucket.append((now or datetime.now(timezone.utc), value))
        self._trim_concurrency(service, now or datetime.now(timezone.utc))

    def compute(self, service: str, *, now: Optional[datetime] = None) -> GoldenSignals:
        now = now or datetime.now(timezone.utc)
        self._trim(service, now)
        self._trim_concurrency(service, now)
        observations = list(self._observations.get(service, []))
        durations = [o.duration_ms for o in observations]
        errors = sum(1 for o in observations if o.is_error)
        seconds = max(self.window.total_seconds(), 1.0)
        concurrency_samples = [v for _, v in self._concurrency.get(service, [])]
        saturation = statistics.mean(concurrency_samples) if concurrency_samples else 0.0
        return GoldenSignals(
            service=service,
            request_rate_per_second=len(observations) / seconds,
            error_rate_percent=(errors / len(observations) * 100.0) if observations else 0.0,
            p50_latency_ms=_percentile(durations, 50),
            p95_latency_ms=_percentile(durations, 95),
            p99_latency_ms=_percentile(durations, 99),
            saturation_percent=min(saturation, 100.0),
            sample_count=len(observations),
        )

    def ingest_spans(self, spans: Iterable[Span]) -> None:
        for span in spans:
            self.record(RequestObservation(
                service=span.service,
                route=span.name,
                duration_ms=span.duration_ms,
                status_code=int(span.attributes.get("http.status_code", 200)),
                timestamp=datetime.fromtimestamp(span.start_ns / 1_000_000_000, tz=timezone.utc),
                upstream=span.attributes.get("upstream"),
            ))

    # -- internals -----------------------------------------------------

    def _trim(self, service: str, now: datetime) -> None:
        bucket = self._observations[service]
        cutoff = now - self.window
        while bucket and bucket[0].timestamp < cutoff:
            bucket.popleft()

    def _trim_concurrency(self, service: str, now: datetime) -> None:
        bucket = self._concurrency[service]
        cutoff = now - self.window
        while bucket and bucket[0][0] < cutoff:
            bucket.popleft()


# -- Service dependency graph -------------------------------------------


class DependencyGraph:
    """Builds a service-to-service call graph from spans."""

    def __init__(self) -> None:
        self._edges: Dict[Tuple[str, str], ServiceEdge] = {}
        self._edge_durations: Dict[Tuple[str, str], List[float]] = defaultdict(list)

    def ingest(self, exporter: InMemoryExporter) -> None:
        for tree in exporter.trees():
            self._walk(tree)

    def edges(self) -> List[ServiceEdge]:
        # Materialize p95 from the accumulated durations.
        for key, edge in self._edges.items():
            edge.p95_latency_ms = _percentile(self._edge_durations.get(key, []), 95)
        return sorted(self._edges.values(), key=lambda e: -e.request_count)

    def services(self) -> List[str]:
        nodes = set()
        for upstream, downstream in self._edges.keys():
            nodes.add(upstream)
            nodes.add(downstream)
        return sorted(nodes)

    def _walk(self, tree: TraceTree) -> None:
        parent = tree.root
        for kids in tree.children.values():
            for child in kids:
                key = (parent.service, child.root.service)
                if parent.service == child.root.service:
                    # Intra-service child; recurse without recording an edge.
                    self._walk(child)
                    continue
                edge = self._edges.setdefault(
                    key, ServiceEdge(upstream=parent.service, downstream=child.root.service),
                )
                edge.request_count += 1
                if child.root.status is SpanStatus.ERROR:
                    edge.error_count += 1
                self._edge_durations[key].append(child.root.duration_ms)
                self._walk(child)


# -- SLO evaluation -----------------------------------------------------


class SLOEvaluator:
    """Computes SLOStatus from a stream of RequestObservations."""

    def __init__(self, slos: List[SLO]):
        self.slos = slos

    def evaluate(
        self,
        observations: Iterable[RequestObservation],
        *,
        now: Optional[datetime] = None,
    ) -> List[SLOStatus]:
        now = now or datetime.now(timezone.utc)
        statuses: List[SLOStatus] = []
        all_obs = list(observations)
        for slo in self.slos:
            window_start = now - timedelta(days=slo.window_days)
            scoped = [
                o for o in all_obs
                if o.service == slo.service and o.timestamp >= window_start
            ]
            if not scoped:
                statuses.append(SLOStatus(
                    slo=slo,
                    observed_availability=1.0,
                    observed_p95_ms=0.0,
                    error_budget_total=1 - slo.availability_target,
                    error_budget_consumed=0.0,
                    burn_rate=0.0,
                    breach=False,
                ))
                continue
            errors = sum(1 for o in scoped if o.is_error)
            total = len(scoped)
            availability = 1 - (errors / total)
            error_budget_total = 1 - slo.availability_target
            observed_error_rate = errors / total
            error_budget_consumed = (
                observed_error_rate / error_budget_total
                if error_budget_total > 0 else 0.0
            )
            # Burn rate: observed errors normalized by allowed window errors.
            burn_rate = (
                observed_error_rate / error_budget_total
                if error_budget_total > 0 else 0.0
            )
            p95 = _percentile([o.duration_ms for o in scoped], slo.latency_target_percentile)
            statuses.append(SLOStatus(
                slo=slo,
                observed_availability=availability,
                observed_p95_ms=p95,
                error_budget_total=error_budget_total,
                error_budget_consumed=min(error_budget_consumed, 1.0),
                burn_rate=burn_rate,
                breach=(
                    availability < slo.availability_target
                    or p95 > slo.latency_target_ms
                ),
            ))
        return statuses


# -- Canary evaluator ---------------------------------------------------


class CanaryEvaluator:
    """Compare canary vs baseline; decide promote / rollback."""

    def __init__(
        self,
        *,
        max_error_rate_increase: float = 0.5,  # percentage points
        max_latency_increase_percent: float = 20.0,
    ):
        self.max_error_rate_increase = max_error_rate_increase
        self.max_latency_increase_percent = max_latency_increase_percent

    def decide(
        self,
        rollout: CanaryRollout,
        baseline: List[RequestObservation],
        candidate: List[RequestObservation],
    ) -> CanaryDecision:
        baseline_error = _error_rate(baseline)
        candidate_error = _error_rate(candidate)
        baseline_p95 = _percentile([o.duration_ms for o in baseline], 95)
        candidate_p95 = _percentile([o.duration_ms for o in candidate], 95)

        latency_pct_increase = (
            ((candidate_p95 - baseline_p95) / baseline_p95) * 100
            if baseline_p95 > 0 else 0.0
        )
        error_increase = candidate_error - baseline_error

        if error_increase > self.max_error_rate_increase:
            return CanaryDecision(
                rollout=rollout,
                baseline_error_rate=baseline_error,
                candidate_error_rate=candidate_error,
                baseline_p95=baseline_p95,
                candidate_p95=candidate_p95,
                promote=False,
                rollback=True,
                rationale=(
                    f"Candidate error rate {candidate_error:.2f}% exceeds baseline "
                    f"by {error_increase:.2f}pp (threshold {self.max_error_rate_increase}pp)"
                ),
            )
        if latency_pct_increase > self.max_latency_increase_percent:
            return CanaryDecision(
                rollout=rollout,
                baseline_error_rate=baseline_error,
                candidate_error_rate=candidate_error,
                baseline_p95=baseline_p95,
                candidate_p95=candidate_p95,
                promote=False,
                rollback=True,
                rationale=(
                    f"Candidate p95 latency {candidate_p95:.1f}ms is "
                    f"{latency_pct_increase:.1f}% over baseline (threshold "
                    f"{self.max_latency_increase_percent}%)"
                ),
            )
        # All checks passed — recommend promotion.
        return CanaryDecision(
            rollout=rollout,
            baseline_error_rate=baseline_error,
            candidate_error_rate=candidate_error,
            baseline_p95=baseline_p95,
            candidate_p95=candidate_p95,
            promote=True,
            rollback=False,
            rationale="Within thresholds; safe to advance weight.",
        )


# -- helpers ------------------------------------------------------------


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return sorted_values[int(k)]
    return sorted_values[lower] * (upper - k) + sorted_values[upper] * (k - lower)


def _error_rate(observations: List[RequestObservation]) -> float:
    if not observations:
        return 0.0
    errors = sum(1 for o in observations if o.is_error)
    return (errors / len(observations)) * 100.0
