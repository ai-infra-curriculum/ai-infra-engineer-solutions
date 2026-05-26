"""
Autoscaler

Combines the metrics collector + forecast + scaler into a single
decision loop. Each tick:

1. Pull current workload metrics.
2. Update the forecaster with the latest queue depth.
3. Compute a ScalingDecision against the configured AutoscalerPolicy.
4. Apply the decision through the Scaler, honoring cooldown.

The policy expresses the four scaling signals that matter for ML
inference: CPU/memory utilization targets, GPU utilization targets,
queue depth thresholds, and a predictive lookahead for proactive scale-up.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .metrics_collector import (
    LinearForecast,
    MetricsCollector,
    WorkloadMetric,
)
from .scaler import ScaleDirection, Scaler, ScalingDecision

logger = logging.getLogger(__name__)


@dataclass
class AutoscalerPolicy:
    """Declarative autoscaling configuration for a workload."""

    workload: str
    namespace: str = "default"
    min_replicas: int = 1
    max_replicas: int = 20
    target_cpu_utilization: float = 0.7
    target_memory_utilization: float = 0.75
    target_gpu_utilization: float = 0.7
    target_queue_depth: float = 10.0
    scale_up_step: int = 2
    scale_down_step: int = 1
    use_predictive_scaling: bool = True
    predictive_horizon_seconds: int = 900
    cost_per_replica_per_hour: float = 0.10


class Autoscaler:
    """Closed-loop autoscaler — periodic tick of collect → decide → act."""

    def __init__(
        self,
        collector: MetricsCollector,
        scaler: Scaler,
        policy: AutoscalerPolicy,
        *,
        forecast: Optional[LinearForecast] = None,
    ):
        self.collector = collector
        self.scaler = scaler
        self.policy = policy
        self.forecast = forecast or LinearForecast()
        self.decision_history: List[ScalingDecision] = []

    def tick(self, *, now: Optional[datetime] = None) -> ScalingDecision:
        """Run one decision cycle and apply the result."""
        metric = self.collector.collect(self.policy.namespace, self.policy.workload)
        self.forecast.observe(self.policy.workload, metric.queue_depth)
        decision = self.decide(metric, now=now)
        self.decision_history.append(decision)
        self.scaler.apply(decision)
        return decision

    def decide(
        self,
        metric: WorkloadMetric,
        *,
        now: Optional[datetime] = None,
    ) -> ScalingDecision:
        """Decide on a scaling action from a metric snapshot."""
        triggers: List[str] = []
        target = metric.replica_count
        reason = "no change required"

        # Signal 1: CPU/memory utilization.
        cpu_target = self._target_replicas_for_utilization(
            metric.avg_cpu, self.policy.target_cpu_utilization, metric.replica_count,
        )
        if cpu_target != metric.replica_count:
            triggers.append(
                f"cpu={metric.avg_cpu:.0%} vs target {self.policy.target_cpu_utilization:.0%}"
            )
            target = max(target, cpu_target) if cpu_target > target else min(target, cpu_target)

        memory_target = self._target_replicas_for_utilization(
            metric.avg_memory, self.policy.target_memory_utilization, metric.replica_count,
        )
        if memory_target > target:
            target = memory_target
            triggers.append(
                f"memory={metric.avg_memory:.0%} vs target {self.policy.target_memory_utilization:.0%}"
            )

        # Signal 2: GPU utilization for GPU workloads.
        if metric.is_gpu_workload:
            gpu_target = self._target_replicas_for_utilization(
                metric.avg_gpu, self.policy.target_gpu_utilization, metric.replica_count,
            )
            if gpu_target > target:
                target = gpu_target
                triggers.append(
                    f"gpu={metric.avg_gpu:.0%} vs target {self.policy.target_gpu_utilization:.0%}"
                )

        # Signal 3: queue depth.
        if metric.queue_depth > self.policy.target_queue_depth:
            queue_target = metric.replica_count + self.policy.scale_up_step
            if queue_target > target:
                target = queue_target
                triggers.append(
                    f"queue={metric.queue_depth:.0f} > target {self.policy.target_queue_depth:.0f}"
                )

        # Signal 4: predictive scale-up.
        if self.policy.use_predictive_scaling:
            forecast = self.forecast.predict(
                self.policy.workload,
                horizon_seconds=self.policy.predictive_horizon_seconds,
            )
            if (
                forecast.confidence >= 0.5
                and forecast.predicted_queue_depth > self.policy.target_queue_depth * 1.5
            ):
                predictive_target = metric.replica_count + self.policy.scale_up_step
                if predictive_target > target:
                    target = predictive_target
                    triggers.append(
                        f"forecast queue={forecast.predicted_queue_depth:.0f} "
                        f"(confidence={forecast.confidence:.0%})"
                    )

        # Clamp to min/max.
        target = max(self.policy.min_replicas, min(self.policy.max_replicas, target))
        # Direction.
        if target > metric.replica_count:
            direction = ScaleDirection.UP
            reason = "scale up due to " + ", ".join(triggers) if triggers else "scale up"
        elif target < metric.replica_count:
            direction = ScaleDirection.DOWN
            target = max(target, metric.replica_count - self.policy.scale_down_step)
            reason = "scale down: utilization below targets"
        else:
            direction = ScaleDirection.HOLD

        cost_delta = (
            (target - metric.replica_count) * self.policy.cost_per_replica_per_hour
        )

        return ScalingDecision(
            workload=self.policy.workload,
            namespace=self.policy.namespace,
            direction=direction,
            from_replicas=metric.replica_count,
            to_replicas=target,
            reason=reason,
            timestamp=now or datetime.now(timezone.utc),
            triggers=triggers,
            cost_delta_per_hour=round(cost_delta, 4),
        )

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _target_replicas_for_utilization(
        observed: float, target: float, current_replicas: int,
    ) -> int:
        if target <= 0:
            return current_replicas
        # HPA formula: desired = ceil(current * (observed / target)).
        ratio = observed / target
        desired = int((current_replicas * ratio) + 0.999)
        return max(1, desired)
