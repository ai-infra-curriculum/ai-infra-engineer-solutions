"""Tests for tracer + metrics_collector."""

import itertools
import time
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from src.metrics_collector import (
    CanaryEvaluator,
    CanaryRollout,
    DependencyGraph,
    GoldenSignalsCollector,
    RequestObservation,
    SLO,
    SLOEvaluator,
    _percentile,
)
from src.tracer import (
    InMemoryExporter,
    NoopExporter,
    SpanKind,
    SpanStatus,
    Tracer,
    build_trace_tree,
)


class TestTracer:
    def test_root_span_has_no_parent(self):
        exporter = InMemoryExporter()
        tracer = Tracer("svc", exporter=exporter)
        span = tracer.start_span("op")
        tracer.end_span(span)
        tracer.flush()
        assert span.parent_span_id is None
        assert span.status is SpanStatus.OK

    def test_child_span_inherits_trace_id(self):
        exporter = InMemoryExporter()
        tracer = Tracer("svc", exporter=exporter)
        root = tracer.start_span("root")
        child = tracer.start_span("child", parent=root)
        assert child.trace_id == root.trace_id
        assert child.parent_span_id == root.span_id

    def test_context_manager_records_exception(self):
        exporter = InMemoryExporter()
        tracer = Tracer("svc", exporter=exporter)
        with pytest.raises(ValueError):
            with tracer.in_span("op") as span:
                raise ValueError("boom")
        tracer.flush()
        recorded = exporter.spans[0]
        assert recorded.status is SpanStatus.ERROR
        assert recorded.attributes["exception.type"] == "ValueError"

    def test_w3c_inject_extract_roundtrip(self):
        tracer = Tracer("svc", exporter=NoopExporter())
        span = tracer.start_span("op")
        headers = {}
        Tracer.inject(span, headers)
        ctx = Tracer.extract(headers)
        assert ctx is not None
        assert ctx.trace_id == span.trace_id
        assert ctx.span_id == span.span_id

    def test_sampler_can_drop_spans(self):
        exporter = InMemoryExporter()
        tracer = Tracer("svc", exporter=exporter, sampler=lambda t: False)
        span = tracer.start_span("op")
        tracer.end_span(span)
        tracer.flush()
        assert not exporter.spans

    def test_build_trace_tree_assembles_children(self):
        exporter = InMemoryExporter()
        tracer = Tracer("svc", exporter=exporter)
        root = tracer.start_span("root")
        child1 = tracer.start_span("c1", parent=root)
        child2 = tracer.start_span("c2", parent=root)
        for s in (child2, child1, root):
            tracer.end_span(s)
        tracer.flush()
        tree = build_trace_tree(exporter.spans)
        assert tree.root.span_id == root.span_id
        assert len(tree.flatten()) == 3


class TestGoldenSignals:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def test_request_rate_computed_over_window(self):
        c = GoldenSignalsCollector(window_seconds=60)
        for i in range(60):
            c.record(RequestObservation(
                service="api", route="/x", duration_ms=10.0,
                status_code=200, timestamp=self._now() - timedelta(seconds=i),
            ))
        signals = c.compute("api")
        assert signals.request_rate_per_second == pytest.approx(1.0, rel=0.1)

    def test_error_rate(self):
        c = GoldenSignalsCollector(window_seconds=300)
        for i in range(100):
            status = 500 if i < 5 else 200
            c.record(RequestObservation(
                service="api", route="/x", duration_ms=10.0,
                status_code=status, timestamp=self._now(),
            ))
        signals = c.compute("api")
        assert signals.error_rate_percent == pytest.approx(5.0)

    def test_percentile_progression(self):
        c = GoldenSignalsCollector(window_seconds=300)
        for ms in range(1, 101):
            c.record(RequestObservation(
                service="api", route="/x", duration_ms=float(ms),
                status_code=200, timestamp=self._now(),
            ))
        signals = c.compute("api")
        assert 49 <= signals.p50_latency_ms <= 51
        assert 94 <= signals.p95_latency_ms <= 96
        assert signals.p95_latency_ms <= signals.p99_latency_ms

    def test_window_trim(self):
        c = GoldenSignalsCollector(window_seconds=10)
        old = self._now() - timedelta(seconds=30)
        c.record(RequestObservation(
            service="api", route="/x", duration_ms=10.0,
            status_code=200, timestamp=old,
        ))
        signals = c.compute("api", now=self._now())
        assert signals.sample_count == 0

    def test_ingest_spans(self):
        exporter = InMemoryExporter()
        tracer = Tracer("api", exporter=exporter)
        span = tracer.start_span("op")
        span.set_attribute("http.status_code", 500)
        tracer.end_span(span, status=SpanStatus.ERROR)
        tracer.flush()
        c = GoldenSignalsCollector(window_seconds=300)
        c.ingest_spans(exporter.spans)
        signals = c.compute("api")
        assert signals.error_rate_percent == 100.0


class TestDependencyGraph:
    def test_records_cross_service_edges(self):
        exporter = InMemoryExporter()
        a = Tracer("a", exporter=exporter)
        b = Tracer("b", exporter=exporter)
        c = Tracer("c", exporter=exporter)
        root = a.start_span("root")
        b_span = b.start_span("b-op", parent=root)
        c_span = c.start_span("c-op", parent=b_span)
        for s in (c_span, b_span, root):
            (a if s.service == "a" else b if s.service == "b" else c).end_span(s)
        for t in (a, b, c):
            t.flush()

        graph = DependencyGraph()
        graph.ingest(exporter)
        edges = graph.edges()
        keys = {(e.upstream, e.downstream) for e in edges}
        assert ("a", "b") in keys
        assert ("b", "c") in keys

    def test_records_errors_per_edge(self):
        exporter = InMemoryExporter()
        gw = Tracer("gw", exporter=exporter)
        backend = Tracer("backend", exporter=exporter)
        for status in [SpanStatus.OK, SpanStatus.ERROR, SpanStatus.ERROR]:
            root = gw.start_span("root")
            child = backend.start_span("call", parent=root)
            backend.end_span(child, status=status)
            gw.end_span(root)
        gw.flush()
        backend.flush()

        graph = DependencyGraph()
        graph.ingest(exporter)
        edge = next(e for e in graph.edges() if e.upstream == "gw")
        assert edge.error_count == 2
        assert edge.error_rate_percent == pytest.approx(66.67, rel=0.01)


class TestSLOEvaluator:
    def test_meets_availability_target(self):
        observations = [
            RequestObservation(
                service="api", route="/x", duration_ms=50.0,
                status_code=200, timestamp=datetime.now(timezone.utc),
            )
            for _ in range(1000)
        ]
        slo = SLO(name="t", service="api", availability_target=0.999, latency_target_ms=200)
        status = SLOEvaluator([slo]).evaluate(observations)[0]
        assert not status.breach
        assert status.observed_availability == pytest.approx(1.0)

    def test_breach_when_error_rate_exceeds_budget(self):
        observations: List[RequestObservation] = []
        for i in range(1000):
            observations.append(RequestObservation(
                service="api", route="/x", duration_ms=50.0,
                status_code=500 if i < 10 else 200,
                timestamp=datetime.now(timezone.utc),
            ))
        slo = SLO(name="t", service="api", availability_target=0.999, latency_target_ms=200)
        status = SLOEvaluator([slo]).evaluate(observations)[0]
        assert status.breach
        # 1% error against 0.1% budget → 10x burn.
        assert status.burn_rate > 5.0

    def test_breach_when_p95_exceeds_target(self):
        observations = [
            RequestObservation(
                service="api", route="/x", duration_ms=500.0,
                status_code=200, timestamp=datetime.now(timezone.utc),
            )
            for _ in range(100)
        ]
        slo = SLO(name="t", service="api", availability_target=0.99, latency_target_ms=100)
        status = SLOEvaluator([slo]).evaluate(observations)[0]
        assert status.breach


class TestCanaryEvaluator:
    def _obs(self, count: int, errors: int, base_latency: float) -> List[RequestObservation]:
        out: List[RequestObservation] = []
        for i in range(count):
            out.append(RequestObservation(
                service="api", route="/x", duration_ms=base_latency,
                status_code=500 if i < errors else 200,
                timestamp=datetime.now(timezone.utc),
            ))
        return out

    def _rollout(self) -> CanaryRollout:
        return CanaryRollout(service="api", baseline_version="v1", candidate_version="v2",
                             candidate_weight_percent=25.0)

    def test_promotes_when_within_thresholds(self):
        baseline = self._obs(1000, 5, 100.0)
        candidate = self._obs(200, 1, 102.0)
        decision = CanaryEvaluator().decide(self._rollout(), baseline, candidate)
        assert decision.promote
        assert not decision.rollback

    def test_rollback_on_error_increase(self):
        baseline = self._obs(1000, 5, 100.0)
        candidate = self._obs(200, 30, 105.0)  # ~15% error rate
        decision = CanaryEvaluator().decide(self._rollout(), baseline, candidate)
        assert decision.rollback
        assert "error rate" in decision.rationale.lower()

    def test_rollback_on_latency_regression(self):
        baseline = self._obs(1000, 0, 100.0)
        candidate = self._obs(200, 0, 200.0)  # 100% latency increase
        decision = CanaryEvaluator().decide(self._rollout(), baseline, candidate)
        assert decision.rollback
        assert "latency" in decision.rationale.lower()

    def test_custom_thresholds(self):
        # Tighter latency threshold rolls back what default would promote.
        baseline = self._obs(100, 0, 100.0)
        candidate = self._obs(100, 0, 115.0)
        # Default tolerates +20%; tighten to +10%.
        decision = CanaryEvaluator(max_latency_increase_percent=10.0).decide(
            self._rollout(), baseline, candidate,
        )
        assert decision.rollback


class TestPercentileHelper:
    def test_empty_returns_zero(self):
        assert _percentile([], 95) == 0.0

    def test_single_value(self):
        assert _percentile([42.0], 95) == 42.0

    def test_known_dataset(self):
        data = list(range(1, 101))
        assert _percentile(data, 50) == pytest.approx(50.5, rel=0.05)
        assert _percentile(data, 99) == pytest.approx(99.01, rel=0.01)
