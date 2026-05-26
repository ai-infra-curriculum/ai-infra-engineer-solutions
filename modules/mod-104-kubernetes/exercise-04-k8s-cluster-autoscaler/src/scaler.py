"""
Scaler

Translates a scaling decision into an action against a target backend.
The backend is a Protocol so the rest of the system stays decoupled from
the kubernetes-python-client. In tests an InMemoryScaler captures the
decisions; in production an HpaScaler patches the Deployment replica
count and/or the HPA target via the apps_v1 + autoscaling_v2 clients.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class ScaleDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    HOLD = "hold"


class CoolingState(str, Enum):
    """Cooldown tracking; prevents rapid up/down flapping."""

    READY = "ready"
    COOLING_DOWN = "cooling_down"
    COOLING_UP = "cooling_up"


@dataclass
class ScalingDecision:
    workload: str
    namespace: str
    direction: ScaleDirection
    from_replicas: int
    to_replicas: int
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggers: List[str] = field(default_factory=list)
    cost_delta_per_hour: float = 0.0


class ScalerBackend(Protocol):
    """How decisions are applied to Kubernetes."""

    def get_replicas(self, namespace: str, workload: str) -> int: ...

    def set_replicas(self, namespace: str, workload: str, replicas: int) -> None: ...


class InMemoryScalerBackend:
    """Reference backend used in tests + CLI demos."""

    def __init__(self) -> None:
        self.state: Dict[str, int] = {}
        self.history: List[ScalingDecision] = []

    def _key(self, namespace: str, workload: str) -> str:
        return f"{namespace}/{workload}"

    def get_replicas(self, namespace: str, workload: str) -> int:
        return self.state.get(self._key(namespace, workload), 1)

    def set_replicas(self, namespace: str, workload: str, replicas: int) -> None:
        self.state[self._key(namespace, workload)] = replicas

    def record(self, decision: ScalingDecision) -> None:
        self.history.append(decision)


class Scaler:
    """Applies ScalingDecisions through a backend, respecting cooldown."""

    def __init__(
        self,
        backend: ScalerBackend,
        *,
        scale_up_cooldown_seconds: int = 60,
        scale_down_cooldown_seconds: int = 300,
    ):
        self.backend = backend
        self.scale_up_cooldown = scale_up_cooldown_seconds
        self.scale_down_cooldown = scale_down_cooldown_seconds
        self._last_action: Dict[str, ScalingDecision] = {}

    def apply(self, decision: ScalingDecision, *, force: bool = False) -> bool:
        """Apply a decision, returning True if the cluster state changed."""
        key = f"{decision.namespace}/{decision.workload}"
        if decision.direction is ScaleDirection.HOLD:
            return False
        if not force and not self._past_cooldown(decision):
            logger.info(
                "Cooldown gate: skipping %s scale-%s for %s",
                decision.direction.value, decision.direction.value, key,
            )
            return False
        self.backend.set_replicas(decision.namespace, decision.workload, decision.to_replicas)
        self._last_action[key] = decision
        if isinstance(self.backend, InMemoryScalerBackend):
            self.backend.record(decision)
        logger.info(
            "Scaled %s: %d → %d (reason=%s)",
            key, decision.from_replicas, decision.to_replicas, decision.reason,
        )
        return True

    def cooling_state(
        self,
        namespace: str,
        workload: str,
        *,
        now: Optional[datetime] = None,
    ) -> CoolingState:
        last = self._last_action.get(f"{namespace}/{workload}")
        if last is None:
            return CoolingState.READY
        elapsed = (now or datetime.now(timezone.utc)) - last.timestamp
        if last.direction is ScaleDirection.UP and elapsed.total_seconds() < self.scale_up_cooldown:
            return CoolingState.COOLING_UP
        if last.direction is ScaleDirection.DOWN and elapsed.total_seconds() < self.scale_down_cooldown:
            return CoolingState.COOLING_DOWN
        return CoolingState.READY

    def _past_cooldown(self, decision: ScalingDecision) -> bool:
        state = self.cooling_state(decision.namespace, decision.workload, now=decision.timestamp)
        if state is CoolingState.READY:
            return True
        if state is CoolingState.COOLING_UP and decision.direction is ScaleDirection.UP:
            return False
        if state is CoolingState.COOLING_DOWN and decision.direction is ScaleDirection.DOWN:
            return False
        return True
