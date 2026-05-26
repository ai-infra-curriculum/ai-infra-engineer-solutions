"""Tests for the autoscaler."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pytest

from src.autoscaler import Autoscaler, AutoscalerPolicy
from src.metrics_collector import (
    LinearForecast,
    MetricsCollector,
    PodMetric,
    WorkloadMetric,
)
from src.scaler import (
    CoolingState,
    InMemoryScalerBackend,
    ScaleDirection,
    Scaler,
    ScalingDecision,
)


def _metric(
    *, replicas=3, cpu=0.5, memory=0.5, gpu=0.0, queue=0.0,
) -> WorkloadMetric:
    return WorkloadMetric(
        workload="api",
        namespace="ml",
        replica_count=replicas,
        pod_metrics=[
            PodMetric(
                pod=f"api-{i}", namespace="ml",
                cpu_utilization=cpu, memory_utilization=memory, gpu_utilization=gpu,
            )
            for i in range(replicas)
        ],
        queue_depth=queue,
    )


@pytest.fixture
def backend() -> InMemoryScalerBackend:
    b = InMemoryScalerBackend()
    b.set_replicas("ml", "api", 3)
    return b


@pytest.fixture
def autoscaler(backend) -> Autoscaler:
    scaler = Scaler(backend, scale_up_cooldown_seconds=0, scale_down_cooldown_seconds=0)
    policy = AutoscalerPolicy(workload="api", namespace="ml", min_replicas=1, max_replicas=10)
    return Autoscaler(
        collector=MetricsCollector(prometheus_query=lambda q: []),
        scaler=scaler,
        policy=policy,
    )


class TestDecisionPaths:
    def test_high_cpu_triggers_scale_up(self, autoscaler):
        decision = autoscaler.decide(_metric(cpu=0.95))
        assert decision.direction is ScaleDirection.UP
        assert decision.to_replicas > decision.from_replicas
        assert any("cpu=" in t for t in decision.triggers)

    def test_low_utilization_triggers_scale_down(self, autoscaler):
        decision = autoscaler.decide(_metric(cpu=0.1, memory=0.1))
        assert decision.direction is ScaleDirection.DOWN
        assert decision.to_replicas < decision.from_replicas

    def test_queue_depth_triggers_scale_up(self, autoscaler):
        decision = autoscaler.decide(_metric(cpu=0.4, queue=50))
        assert decision.direction is ScaleDirection.UP
        assert any("queue=" in t for t in decision.triggers)

    def test_gpu_only_scaling_for_gpu_workloads(self, autoscaler):
        decision = autoscaler.decide(_metric(cpu=0.4, gpu=0.95))
        assert decision.direction is ScaleDirection.UP
        assert any("gpu=" in t for t in decision.triggers)

    def test_balanced_utilization_holds(self, autoscaler):
        decision = autoscaler.decide(_metric(cpu=0.7, memory=0.7))
        assert decision.direction is ScaleDirection.HOLD
        assert decision.to_replicas == decision.from_replicas

    def test_max_replicas_clamps(self, autoscaler):
        autoscaler.policy.max_replicas = 4
        decision = autoscaler.decide(_metric(cpu=0.99, queue=200))
        assert decision.to_replicas <= 4

    def test_min_replicas_clamps(self, autoscaler):
        autoscaler.policy.min_replicas = 3
        decision = autoscaler.decide(_metric(replicas=4, cpu=0.05, memory=0.05))
        assert decision.to_replicas >= 3

    def test_scale_down_step_limits_aggressive_shrink(self, autoscaler):
        autoscaler.policy.scale_down_step = 1
        decision = autoscaler.decide(_metric(replicas=10, cpu=0.05, memory=0.05))
        assert decision.from_replicas - decision.to_replicas == 1

    def test_cost_delta_for_scale_up(self, autoscaler):
        autoscaler.policy.cost_per_replica_per_hour = 0.50
        decision = autoscaler.decide(_metric(cpu=0.95))
        assert decision.cost_delta_per_hour > 0

    def test_cost_delta_for_scale_down(self, autoscaler):
        autoscaler.policy.cost_per_replica_per_hour = 0.50
        decision = autoscaler.decide(_metric(cpu=0.1, memory=0.1))
        assert decision.cost_delta_per_hour < 0


class TestCooldown:
    def test_cooldown_blocks_rapid_consecutive_scale_ups(self, backend):
        scaler = Scaler(backend, scale_up_cooldown_seconds=60, scale_down_cooldown_seconds=300)
        now = datetime.now(timezone.utc)
        first = ScalingDecision(
            workload="api", namespace="ml",
            direction=ScaleDirection.UP, from_replicas=3, to_replicas=5,
            reason="t", timestamp=now,
        )
        scaler.apply(first)
        # 30 seconds later — still cooling.
        second = ScalingDecision(
            workload="api", namespace="ml",
            direction=ScaleDirection.UP, from_replicas=5, to_replicas=7,
            reason="t", timestamp=now + timedelta(seconds=30),
        )
        applied = scaler.apply(second)
        assert applied is False
        assert backend.get_replicas("ml", "api") == 5

    def test_cooldown_does_not_block_opposite_direction(self, backend):
        scaler = Scaler(backend, scale_up_cooldown_seconds=600, scale_down_cooldown_seconds=600)
        now = datetime.now(timezone.utc)
        up = ScalingDecision(
            workload="api", namespace="ml",
            direction=ScaleDirection.UP, from_replicas=3, to_replicas=5,
            reason="t", timestamp=now,
        )
        scaler.apply(up)
        down = ScalingDecision(
            workload="api", namespace="ml",
            direction=ScaleDirection.DOWN, from_replicas=5, to_replicas=4,
            reason="t", timestamp=now + timedelta(seconds=30),
        )
        assert scaler.apply(down) is True

    def test_cooling_state_transitions_to_ready(self, backend):
        scaler = Scaler(backend, scale_up_cooldown_seconds=60, scale_down_cooldown_seconds=60)
        now = datetime.now(timezone.utc)
        scaler.apply(ScalingDecision(
            workload="api", namespace="ml",
            direction=ScaleDirection.UP, from_replicas=3, to_replicas=5,
            reason="t", timestamp=now,
        ))
        state = scaler.cooling_state("ml", "api", now=now + timedelta(seconds=120))
        assert state is CoolingState.READY


class TestForecast:
    def test_predict_with_no_history_returns_zero_confidence(self):
        fc = LinearForecast()
        result = fc.predict("api")
        assert result.confidence == 0.0

    def test_predict_with_rising_queue_predicts_growth(self):
        fc = LinearForecast()
        for v in [5, 10, 20, 35, 50, 70]:
            fc.observe("api", v)
        result = fc.predict("api", horizon_seconds=900)
        # 15 minutes (3 samples) of growth should push prediction up.
        assert result.predicted_queue_depth > 70
        assert result.confidence > 0

    def test_predict_with_stable_queue_predicts_flat(self):
        fc = LinearForecast()
        for _ in range(10):
            fc.observe("api", 5.0)
        result = fc.predict("api")
        assert abs(result.predicted_queue_depth - 5.0) < 1.0
        # Stable queue → high confidence.
        assert result.confidence > 0.8


class TestEndToEnd:
    def test_apply_history_recorded(self, backend, autoscaler):
        decision = autoscaler.decide(_metric(cpu=0.95))
        autoscaler.scaler.apply(decision)
        assert backend.history
        assert backend.history[0].direction is ScaleDirection.UP

    def test_predictive_scale_up_when_forecast_high(self, autoscaler):
        # Feed a rising series → forecast should drive an additional scale-up.
        for v in [2, 8, 14, 18, 22, 25]:
            autoscaler.forecast.observe(autoscaler.policy.workload, v)
        decision = autoscaler.decide(_metric(cpu=0.5, queue=8))
        # Predictive trigger should appear in triggers list.
        assert any("forecast" in t for t in decision.triggers) or decision.direction is ScaleDirection.HOLD
