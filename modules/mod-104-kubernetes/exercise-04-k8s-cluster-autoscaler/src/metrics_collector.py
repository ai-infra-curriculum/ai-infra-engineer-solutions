"""
Metrics Collector

Pulls the ML-specific signals the autoscaler reasons about:
- pod CPU + memory utilization (from kube-state-metrics / metrics-server),
- per-pod GPU utilization (from dcgm-exporter or nvidia-smi),
- inference queue depth + latency p95 (from the model server's Prometheus exposition),
- horizontal pod replica count (from the kube apiserver).

The collector accepts a `prometheus_query` callable so the rest of the
system stays decoupled from the HTTP client. In tests a stub callable
yields canned responses; in production it points at a real Prometheus
endpoint via the `prometheus_api_client` library.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PodMetric:
    """Resource utilization for a single pod, normalized to 0-1."""

    pod: str
    namespace: str
    cpu_utilization: float  # 0.0 .. 1.0 (fraction of requested CPU)
    memory_utilization: float
    gpu_utilization: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WorkloadMetric:
    """Workload-level signals across a deployment."""

    workload: str
    namespace: str
    replica_count: int
    pod_metrics: List[PodMetric]
    queue_depth: float = 0.0
    p95_latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def avg_cpu(self) -> float:
        if not self.pod_metrics:
            return 0.0
        return statistics.mean(p.cpu_utilization for p in self.pod_metrics)

    @property
    def avg_memory(self) -> float:
        if not self.pod_metrics:
            return 0.0
        return statistics.mean(p.memory_utilization for p in self.pod_metrics)

    @property
    def avg_gpu(self) -> float:
        if not self.pod_metrics:
            return 0.0
        return statistics.mean(p.gpu_utilization for p in self.pod_metrics)

    @property
    def is_gpu_workload(self) -> bool:
        return any(p.gpu_utilization > 0 for p in self.pod_metrics)


PromQueryFn = Callable[[str], List[Dict[str, float]]]


class MetricsCollector:
    """Collects metrics for a workload by issuing Prometheus queries."""

    def __init__(self, prometheus_query: PromQueryFn):
        self.prom = prometheus_query

    def collect(self, namespace: str, workload: str) -> WorkloadMetric:
        """Pull pod-level + workload-level signals."""
        pod_records = self._collect_pods(namespace, workload)
        replicas_query = (
            f'kube_deployment_status_replicas{{namespace="{namespace}",'
            f'deployment="{workload}"}}'
        )
        replica_count = int(self._scalar(replicas_query, default=len(pod_records)))

        queue_query = (
            f'model_inference_queue_depth{{namespace="{namespace}",'
            f'workload="{workload}"}}'
        )
        queue_depth = self._scalar(queue_query, default=0.0)

        latency_query = (
            f'histogram_quantile(0.95, '
            f'rate(model_inference_latency_seconds_bucket{{'
            f'namespace="{namespace}",workload="{workload}"}}[5m]))'
        )
        latency = self._scalar(latency_query, default=0.0) * 1000.0  # → ms

        return WorkloadMetric(
            workload=workload,
            namespace=namespace,
            replica_count=replica_count,
            pod_metrics=pod_records,
            queue_depth=queue_depth,
            p95_latency_ms=latency,
        )

    # -- internals -----------------------------------------------------

    def _collect_pods(self, namespace: str, workload: str) -> List[PodMetric]:
        cpu = self._labeled(
            f'rate(container_cpu_usage_seconds_total{{'
            f'namespace="{namespace}",pod=~"{workload}-.*"}}[5m]) / '
            f'on(pod) kube_pod_container_resource_requests_cpu_cores'
        )
        mem = self._labeled(
            f'container_memory_working_set_bytes{{'
            f'namespace="{namespace}",pod=~"{workload}-.*"}} / '
            f'on(pod) kube_pod_container_resource_requests_memory_bytes'
        )
        gpu = self._labeled(
            f'DCGM_FI_DEV_GPU_UTIL{{namespace="{namespace}",'
            f'pod=~"{workload}-.*"}} / 100'
        )

        pods = set(cpu) | set(mem) | set(gpu)
        out: List[PodMetric] = []
        for pod in sorted(pods):
            out.append(PodMetric(
                pod=pod,
                namespace=namespace,
                cpu_utilization=cpu.get(pod, 0.0),
                memory_utilization=mem.get(pod, 0.0),
                gpu_utilization=gpu.get(pod, 0.0),
            ))
        return out

    def _scalar(self, query: str, default: float) -> float:
        results = self.prom(query)
        if not results:
            return default
        return float(results[0].get("value", default))

    def _labeled(self, query: str) -> Dict[str, float]:
        results = self.prom(query)
        labeled: Dict[str, float] = {}
        for entry in results:
            pod = entry.get("pod")
            value = entry.get("value")
            if pod is not None and value is not None:
                labeled[pod] = float(value)
        return labeled


# -- Predictive forecast --------------------------------------------------


@dataclass
class ForecastResult:
    """Predicted load 15 minutes ahead."""

    workload: str
    horizon_seconds: int
    predicted_queue_depth: float
    predicted_replica_count: int
    confidence: float  # 0.0 .. 1.0


class LinearForecast:
    """A small EMA + slope forecast: enough to demonstrate proactive scaling.

    The forecast is intentionally lightweight (no numpy / no statsmodels)
    so the autoscaler stays auditable. Production deployments swap this
    out for Prophet, NeuralProphet, or vendor-managed time-series.
    """

    def __init__(self, *, alpha: float = 0.3):
        self.alpha = alpha
        self._history: Dict[str, List[float]] = {}

    def observe(self, workload: str, queue_depth: float) -> None:
        self._history.setdefault(workload, []).append(queue_depth)
        # Cap history at last 24 samples (~2h at 5-min cadence).
        self._history[workload] = self._history[workload][-24:]

    def predict(
        self,
        workload: str,
        *,
        horizon_seconds: int = 900,
        sample_interval_seconds: int = 300,
    ) -> ForecastResult:
        history = self._history.get(workload, [])
        if len(history) < 3:
            return ForecastResult(
                workload=workload,
                horizon_seconds=horizon_seconds,
                predicted_queue_depth=history[-1] if history else 0.0,
                predicted_replica_count=0,
                confidence=0.0,
            )
        # Slope from last 3 samples.
        recent = history[-3:]
        slope = (recent[-1] - recent[0]) / 2
        ema = recent[-1]
        for v in reversed(recent[:-1]):
            ema = self.alpha * v + (1 - self.alpha) * ema
        horizon_samples = horizon_seconds / sample_interval_seconds
        predicted = max(ema + slope * horizon_samples, 0.0)
        # Confidence falls off as variance grows.
        variance = statistics.pvariance(history)
        confidence = max(0.1, 1.0 - min(variance / 100.0, 0.9))
        return ForecastResult(
            workload=workload,
            horizon_seconds=horizon_seconds,
            predicted_queue_depth=predicted,
            predicted_replica_count=0,
            confidence=confidence,
        )
