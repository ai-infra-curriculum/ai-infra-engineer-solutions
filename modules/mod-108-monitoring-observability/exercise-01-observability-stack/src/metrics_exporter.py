"""
Prometheus-Compatible Metrics Exporter

A small framework-free implementation of the Prometheus exposition
format with the four standard metric types (counter, gauge, histogram,
summary), label support, and a /metrics HTTP-style serializer.

This module is intentionally dependency-free (no prometheus_client) so
it ships with the curriculum solution as auditable reference code. In
production a real exporter would compose around prometheus_client, but
the semantics implemented here match the OpenMetrics 1.0 contract.

Includes:
- Registry with concurrent-safe metric registration.
- Counters / Gauges / Histograms (with configurable buckets) /
  Summaries (with rolling-window quantile observations).
- Structured-log emission helpers compatible with Loki ingestion.
- SLO tracker + error-budget calculator built on top.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Deque, Dict, Iterable, List, Optional, Tuple


logger = logging.getLogger(__name__)


# -- Metric base types --------------------------------------------------


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


_LabelValues = Tuple[Tuple[str, str], ...]


def _label_key(labels: Optional[Dict[str, str]]) -> _LabelValues:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def _format_labels(labels: _LabelValues) -> str:
    if not labels:
        return ""
    return "{" + ",".join(f'{k}="{_escape(v)}"' for k, v in labels) + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")


# -- Counter ------------------------------------------------------------


class Counter:
    """Monotonically-increasing counter."""

    def __init__(self, name: str, help_text: str, *, label_names: Optional[List[str]] = None):
        self.name = name
        self.help_text = help_text
        self.label_names = list(label_names or [])
        self._values: Dict[_LabelValues, float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, *, labels: Optional[Dict[str, str]] = None) -> None:
        if amount < 0:
            raise ValueError("Counter increment must be non-negative")
        with self._lock:
            key = _label_key(labels)
            self._values[key] = self._values.get(key, 0.0) + amount

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        with self._lock:
            return self._values.get(_label_key(labels), 0.0)

    def emit(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help_text}"
        yield f"# TYPE {self.name} counter"
        with self._lock:
            items = list(self._values.items())
        for key, value in items:
            yield f"{self.name}{_format_labels(key)} {value}"


# -- Gauge --------------------------------------------------------------


class Gauge:
    """A value that can go up or down."""

    def __init__(self, name: str, help_text: str, *, label_names: Optional[List[str]] = None):
        self.name = name
        self.help_text = help_text
        self.label_names = list(label_names or [])
        self._values: Dict[_LabelValues, float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, *, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self._values[_label_key(labels)] = float(value)

    def inc(self, amount: float = 1.0, *, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            key = _label_key(labels)
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, *, labels: Optional[Dict[str, str]] = None) -> None:
        self.inc(-amount, labels=labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        with self._lock:
            return self._values.get(_label_key(labels), 0.0)

    def emit(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help_text}"
        yield f"# TYPE {self.name} gauge"
        with self._lock:
            items = list(self._values.items())
        for key, value in items:
            yield f"{self.name}{_format_labels(key)} {value}"


# -- Histogram ----------------------------------------------------------


DEFAULT_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


@dataclass
class _HistogramState:
    counts: Dict[float, int] = field(default_factory=dict)
    sum: float = 0.0
    total: int = 0


class Histogram:
    """Histogram with explicit upper-bound buckets."""

    def __init__(
        self,
        name: str,
        help_text: str,
        *,
        buckets: Tuple[float, ...] = DEFAULT_BUCKETS,
        label_names: Optional[List[str]] = None,
    ):
        self.name = name
        self.help_text = help_text
        self.label_names = list(label_names or [])
        self.buckets = tuple(sorted(buckets))
        self._states: Dict[_LabelValues, _HistogramState] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, *, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            key = _label_key(labels)
            state = self._states.setdefault(key, _HistogramState())
            state.sum += value
            state.total += 1
            for upper in self.buckets:
                if value <= upper:
                    state.counts[upper] = state.counts.get(upper, 0) + 1

    def snapshot(
        self, *, labels: Optional[Dict[str, str]] = None,
    ) -> Dict[float, int]:
        with self._lock:
            state = self._states.get(_label_key(labels))
            return dict(state.counts) if state else {}

    def total_observations(self, *, labels: Optional[Dict[str, str]] = None) -> int:
        with self._lock:
            state = self._states.get(_label_key(labels))
            return state.total if state else 0

    def quantile(self, q: float, *, labels: Optional[Dict[str, str]] = None) -> float:
        """Approximate quantile from cumulative bucket counts.

        observe() stores counts cumulatively (a value of 0.05 increments
        every bucket whose upper bound >= 0.05). So the quantile is the
        first bucket whose count exceeds total * q.
        """
        if not 0.0 < q < 1.0:
            raise ValueError(f"quantile must be in (0, 1), got {q}")
        with self._lock:
            state = self._states.get(_label_key(labels))
            if state is None or state.total == 0:
                return 0.0
            target = state.total * q
            for upper in self.buckets:
                if state.counts.get(upper, 0) >= target:
                    return upper
            return self.buckets[-1] if self.buckets else 0.0

    def emit(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help_text}"
        yield f"# TYPE {self.name} histogram"
        with self._lock:
            items = list(self._states.items())
        for key, state in items:
            # observe() stores cumulative counts (one increment per
            # bucket whose upper bound covers the value), so emit them
            # directly without re-cumulating.
            for upper in self.buckets:
                count = state.counts.get(upper, 0)
                label_str = _format_labels(key + (("le", str(upper)),))
                yield f"{self.name}_bucket{label_str} {count}"
            inf_label = _format_labels(key + (("le", "+Inf"),))
            yield f"{self.name}_bucket{inf_label} {state.total}"
            yield f"{self.name}_sum{_format_labels(key)} {state.sum}"
            yield f"{self.name}_count{_format_labels(key)} {state.total}"


# -- Summary -----------------------------------------------------------


class Summary:
    """Rolling-window summary with sample-based quantiles."""

    def __init__(
        self,
        name: str,
        help_text: str,
        *,
        window_size: int = 1024,
        quantiles: Tuple[float, ...] = (0.5, 0.9, 0.95, 0.99),
        label_names: Optional[List[str]] = None,
    ):
        self.name = name
        self.help_text = help_text
        self.label_names = list(label_names or [])
        self.window_size = window_size
        self.quantiles = quantiles
        self._observations: Dict[_LabelValues, Deque[float]] = {}
        self._totals: Dict[_LabelValues, Tuple[int, float]] = {}  # (count, sum)
        self._lock = threading.Lock()

    def observe(self, value: float, *, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            key = _label_key(labels)
            window = self._observations.setdefault(key, deque(maxlen=self.window_size))
            window.append(value)
            count, total = self._totals.get(key, (0, 0.0))
            self._totals[key] = (count + 1, total + value)

    def emit(self) -> Iterable[str]:
        yield f"# HELP {self.name} {self.help_text}"
        yield f"# TYPE {self.name} summary"
        with self._lock:
            items = list(self._observations.items())
            totals = dict(self._totals)
        for key, window in items:
            sorted_window = sorted(window)
            for q in self.quantiles:
                quantile_value = _percentile(sorted_window, q * 100.0)
                label_str = _format_labels(key + (("quantile", str(q)),))
                yield f"{self.name}{label_str} {quantile_value}"
            count, total = totals.get(key, (0, 0.0))
            yield f"{self.name}_sum{_format_labels(key)} {total}"
            yield f"{self.name}_count{_format_labels(key)} {count}"


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


# -- Registry ----------------------------------------------------------


class MetricsRegistry:
    """Registers metrics and produces OpenMetrics-style exposition output."""

    def __init__(self) -> None:
        self._metrics: Dict[str, object] = {}
        self._lock = threading.Lock()

    def register(self, metric) -> object:
        with self._lock:
            if metric.name in self._metrics:
                existing = self._metrics[metric.name]
                if type(existing) is not type(metric):
                    raise ValueError(
                        f"Metric {metric.name!r} already registered as "
                        f"{type(existing).__name__}, refusing to override "
                        f"with {type(metric).__name__}"
                    )
                return existing
            self._metrics[metric.name] = metric
            return metric

    def counter(self, name: str, help_text: str, *, label_names: Optional[List[str]] = None) -> Counter:
        return self.register(Counter(name, help_text, label_names=label_names))

    def gauge(self, name: str, help_text: str, *, label_names: Optional[List[str]] = None) -> Gauge:
        return self.register(Gauge(name, help_text, label_names=label_names))

    def histogram(
        self,
        name: str,
        help_text: str,
        *,
        buckets: Tuple[float, ...] = DEFAULT_BUCKETS,
        label_names: Optional[List[str]] = None,
    ) -> Histogram:
        return self.register(Histogram(name, help_text, buckets=buckets, label_names=label_names))

    def summary(
        self,
        name: str,
        help_text: str,
        *,
        window_size: int = 1024,
        label_names: Optional[List[str]] = None,
    ) -> Summary:
        return self.register(Summary(
            name, help_text, window_size=window_size, label_names=label_names,
        ))

    def expose(self) -> str:
        """Render all metrics in Prometheus exposition format."""
        lines: List[str] = []
        for metric in self._metrics.values():
            lines.extend(metric.emit())
        return "\n".join(lines) + "\n"

    def names(self) -> List[str]:
        return sorted(self._metrics.keys())


# -- Structured logging (Loki-compatible) ------------------------------


@dataclass
class StructuredLogRecord:
    timestamp: datetime
    level: str
    service: str
    message: str
    fields: Dict[str, object] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = {
            "ts": self.timestamp.isoformat(),
            "level": self.level,
            "service": self.service,
            "msg": self.message,
            **self.fields,
        }
        return json.dumps(payload, default=str, sort_keys=True)


class StructuredLogger:
    """Emit structured JSON log records ready for Loki ingestion."""

    def __init__(self, service: str):
        self.service = service
        self.records: List[StructuredLogRecord] = []

    def log(self, level: str, message: str, **fields) -> StructuredLogRecord:
        record = StructuredLogRecord(
            timestamp=datetime.now(timezone.utc),
            level=level.upper(),
            service=self.service,
            message=message,
            fields=fields,
        )
        self.records.append(record)
        return record


# -- SLO + error budget ------------------------------------------------


@dataclass
class SLO:
    """One SLO target (availability + latency)."""

    name: str
    target_availability: float = 0.999
    target_latency_p95_ms: Optional[float] = None
    window_days: int = 30


@dataclass
class SLOSnapshot:
    """Current SLO status."""

    slo: SLO
    observed_availability: float
    observed_p95_latency_ms: Optional[float]
    error_budget_remaining_percent: float
    burn_rate: float
    breached: bool


class SLOTracker:
    """Tracks request outcomes + latencies for one service."""

    def __init__(self, slo: SLO):
        self.slo = slo
        self._total = 0
        self._errors = 0
        self._latencies: Deque[float] = deque(maxlen=10000)

    def record(self, *, success: bool, latency_ms: Optional[float] = None) -> None:
        self._total += 1
        if not success:
            self._errors += 1
        if latency_ms is not None:
            self._latencies.append(latency_ms)

    def snapshot(self) -> SLOSnapshot:
        if self._total == 0:
            return SLOSnapshot(
                slo=self.slo, observed_availability=1.0,
                observed_p95_latency_ms=None,
                error_budget_remaining_percent=100.0,
                burn_rate=0.0,
                breached=False,
            )
        availability = 1.0 - (self._errors / self._total)
        budget_total = 1.0 - self.slo.target_availability
        observed_error_rate = self._errors / self._total
        remaining = (
            ((budget_total - observed_error_rate) / budget_total) * 100.0
            if budget_total > 0 else 100.0
        )
        burn_rate = observed_error_rate / budget_total if budget_total > 0 else 0.0
        observed_p95 = (
            _percentile(sorted(self._latencies), 95.0) if self._latencies else None
        )
        breached = availability < self.slo.target_availability or (
            self.slo.target_latency_p95_ms is not None
            and observed_p95 is not None
            and observed_p95 > self.slo.target_latency_p95_ms
        )
        return SLOSnapshot(
            slo=self.slo,
            observed_availability=round(availability, 6),
            observed_p95_latency_ms=round(observed_p95, 2) if observed_p95 is not None else None,
            error_budget_remaining_percent=round(remaining, 2),
            burn_rate=round(burn_rate, 3),
            breached=breached,
        )
