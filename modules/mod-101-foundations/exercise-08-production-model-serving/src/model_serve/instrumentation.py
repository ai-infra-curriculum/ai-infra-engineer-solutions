"""Custom Prometheus metrics."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


PREDICTIONS = Counter(
    "predictions_total", "Total predictions", ["status", "model_version"],
)

PREDICT_LATENCY = Histogram(
    "predict_latency_seconds", "Inference latency",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

INFLIGHT = Gauge("inflight_requests", "In-flight requests")

MODEL_INFO = Gauge("model_info", "Loaded model info", ["version"])
