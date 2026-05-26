"""Tests for the metrics exporter, SLO tracker, and structured logger."""

import json
from typing import List

import pytest

from src.metrics_exporter import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    SLO,
    SLOTracker,
    StructuredLogger,
    Summary,
)


class TestCounter:
    def test_inc_adds(self):
        c = Counter("requests", "total requests")
        c.inc()
        c.inc(2)
        assert c.get() == 3

    def test_negative_inc_rejected(self):
        c = Counter("requests", "total requests")
        with pytest.raises(ValueError):
            c.inc(-1)

    def test_labels_keyed_separately(self):
        c = Counter("requests", "h", label_names=["method"])
        c.inc(labels={"method": "GET"})
        c.inc(labels={"method": "POST"})
        c.inc(labels={"method": "GET"})
        assert c.get(labels={"method": "GET"}) == 2
        assert c.get(labels={"method": "POST"}) == 1

    def test_exposition_format(self):
        c = Counter("foo_total", "demo", label_names=["x"])
        c.inc(5, labels={"x": "a"})
        lines = list(c.emit())
        assert any("foo_total" in l for l in lines)
        assert any('foo_total{x="a"} 5' in l for l in lines)


class TestGauge:
    def test_set_and_get(self):
        g = Gauge("temp", "temperature")
        g.set(42.5)
        assert g.get() == 42.5

    def test_inc_dec(self):
        g = Gauge("in_flight", "in-flight requests")
        g.inc()
        g.inc()
        g.dec()
        assert g.get() == 1.0


class TestHistogram:
    def test_observe_buckets(self):
        h = Histogram("latency", "latency seconds", buckets=(0.1, 0.5, 1.0))
        for v in [0.05, 0.2, 0.4, 0.6, 1.5]:
            h.observe(v)
        snap = h.snapshot()
        assert snap[0.1] == 1  # 0.05
        assert snap[0.5] == 3  # 0.05, 0.2, 0.4
        assert snap[1.0] == 4  # + 0.6
        assert h.total_observations() == 5

    def test_quantile(self):
        h = Histogram("latency", "h", buckets=(0.1, 0.25, 0.5, 1.0, 2.5))
        for _ in range(80):
            h.observe(0.1)
        for _ in range(15):
            h.observe(0.5)
        for _ in range(5):
            h.observe(2.0)
        # 95th percentile ≈ 0.5 or higher.
        q95 = h.quantile(0.95)
        assert q95 >= 0.5

    def test_quantile_out_of_range(self):
        h = Histogram("latency", "h")
        with pytest.raises(ValueError):
            h.quantile(1.5)

    def test_exposition_includes_inf_bucket(self):
        h = Histogram("latency_seconds", "h", buckets=(0.1, 0.5))
        h.observe(0.05)
        h.observe(0.4)
        h.observe(5.0)
        lines = list(h.emit())
        assert any("latency_seconds_bucket" in l for l in lines)
        assert any('le="+Inf"' in l for l in lines)
        assert any("latency_seconds_sum" in l for l in lines)


class TestSummary:
    def test_quantiles_in_exposition(self):
        s = Summary("op_seconds", "h", window_size=100,
                    quantiles=(0.5, 0.95))
        for i in range(100):
            s.observe(i / 100.0)
        lines = list(s.emit())
        assert any('quantile="0.5"' in l for l in lines)
        assert any('quantile="0.95"' in l for l in lines)


class TestRegistry:
    def test_register_returns_same_metric_on_duplicate_name(self):
        r = MetricsRegistry()
        c1 = r.counter("rc", "h")
        c2 = r.counter("rc", "h")
        assert c1 is c2

    def test_register_rejects_type_change(self):
        r = MetricsRegistry()
        r.counter("rc", "h")
        with pytest.raises(ValueError):
            r.gauge("rc", "different type")

    def test_expose_renders_all_metrics(self):
        r = MetricsRegistry()
        r.counter("requests_total", "h")
        r.gauge("ready", "ready")
        text = r.expose()
        assert "# TYPE requests_total counter" in text
        assert "# TYPE ready gauge" in text


class TestSLOTracker:
    def test_no_observations_full_budget(self):
        tracker = SLOTracker(SLO(name="x", target_availability=0.999))
        snap = tracker.snapshot()
        assert snap.error_budget_remaining_percent == 100.0
        assert not snap.breached

    def test_within_budget(self):
        tracker = SLOTracker(SLO(name="x", target_availability=0.99))
        for i in range(1000):
            tracker.record(success=(i >= 5))  # 5 errors / 1000 = 0.5%
        snap = tracker.snapshot()
        assert not snap.breached
        assert snap.observed_availability == pytest.approx(0.995)

    def test_breach_when_availability_below_target(self):
        tracker = SLOTracker(SLO(name="x", target_availability=0.999))
        for i in range(1000):
            tracker.record(success=(i >= 50))  # 5% errors
        snap = tracker.snapshot()
        assert snap.breached
        assert snap.burn_rate > 1.0

    def test_breach_on_latency(self):
        tracker = SLOTracker(SLO(
            name="x", target_availability=0.99, target_latency_p95_ms=100.0,
        ))
        for _ in range(100):
            tracker.record(success=True, latency_ms=250.0)
        snap = tracker.snapshot()
        assert snap.breached

    def test_remaining_budget_decreases_with_errors(self):
        tracker = SLOTracker(SLO(name="x", target_availability=0.99))
        for i in range(100):
            tracker.record(success=(i >= 0))  # 0 errors → 100% remaining
        snap_clean = tracker.snapshot()
        assert snap_clean.error_budget_remaining_percent == pytest.approx(100.0)


class TestStructuredLogger:
    def test_log_returns_json_with_fields(self):
        logger_ = StructuredLogger("svc")
        record = logger_.log("INFO", "hello", path="/v1", status=200)
        payload = json.loads(record.to_json())
        assert payload["level"] == "INFO"
        assert payload["service"] == "svc"
        assert payload["msg"] == "hello"
        assert payload["path"] == "/v1"
        assert payload["status"] == 200

    def test_records_accumulate(self):
        logger_ = StructuredLogger("svc")
        for i in range(5):
            logger_.log("INFO", f"msg-{i}")
        assert len(logger_.records) == 5


class TestExpositionFormat:
    def test_label_escaping(self):
        r = MetricsRegistry()
        c = r.counter("foo", "h", label_names=["x"])
        # Embed a quote in the label value to verify escaping.
        c.inc(labels={"x": 'a"b'})
        text = r.expose()
        assert r'a\"b' in text
