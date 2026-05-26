"""
Custom Resource Definition for ModelDeployment

Defines the typed Python representation of the `models.ml.example.com/v1`
ModelDeployment CRD. Operators receive raw Kubernetes objects as dicts;
this module parses them into ModelDeploymentSpec / ModelDeploymentStatus
dataclasses, validates the shape, and serializes back to dicts for
status updates.

The CRD itself is a YAML manifest applied separately to the cluster;
this module describes the schema and ships with `to_openapi_v3` that
emits the CRD's OpenAPIV3Schema fragment so callers can regenerate the
manifest in CI.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

CRD_GROUP = "ml.example.com"
CRD_VERSION = "v1"
CRD_KIND = "ModelDeployment"
CRD_PLURAL = "modeldeployments"

# Kubernetes object-name pattern (RFC 1123 label).
_NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")


class DeploymentPhase(str, Enum):
    PENDING = "Pending"
    DEPLOYING = "Deploying"
    READY = "Ready"
    DEGRADED = "Degraded"
    FAILED = "Failed"
    ROLLED_BACK = "RolledBack"


class TrafficStrategy(str, Enum):
    BLUE_GREEN = "BlueGreen"
    CANARY = "Canary"
    SHADOW = "Shadow"


@dataclass
class ResourceRequest:
    cpu: str = "500m"
    memory: str = "1Gi"
    gpu: int = 0  # nvidia.com/gpu


@dataclass
class AutoscalingSpec:
    enabled: bool = True
    min_replicas: int = 1
    max_replicas: int = 10
    target_cpu_utilization: int = 70
    target_queue_depth: Optional[int] = None


@dataclass
class ModelDeploymentSpec:
    """Spec body of a ModelDeployment CR."""

    model_name: str
    version: str
    image: str
    replicas: int = 2
    resources: ResourceRequest = field(default_factory=ResourceRequest)
    autoscaling: AutoscalingSpec = field(default_factory=AutoscalingSpec)
    serving_port: int = 8000
    health_check_path: str = "/healthz"
    readiness_check_path: str = "/ready"
    traffic_strategy: TrafficStrategy = TrafficStrategy.BLUE_GREEN
    canary_weight_percent: int = 0
    previous_version: Optional[str] = None  # rollback target
    env: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Condition:
    """K8s-style condition entry."""

    type: str
    status: str  # "True" / "False" / "Unknown"
    reason: str = ""
    message: str = ""
    last_transition_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "status": self.status,
            "reason": self.reason,
            "message": self.message,
            "lastTransitionTime": self.last_transition_time.isoformat(),
        }


@dataclass
class ModelDeploymentStatus:
    """Status sub-resource of a ModelDeployment."""

    phase: DeploymentPhase = DeploymentPhase.PENDING
    observed_generation: int = 0
    ready_replicas: int = 0
    desired_replicas: int = 0
    deployed_version: Optional[str] = None
    canary_version: Optional[str] = None
    conditions: List[Condition] = field(default_factory=list)
    last_reconciled: Optional[datetime] = None
    failure_count: int = 0

    def set_condition(self, condition: Condition) -> None:
        # Replace any existing condition of the same type.
        self.conditions = [c for c in self.conditions if c.type != condition.type]
        self.conditions.append(condition)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "observedGeneration": self.observed_generation,
            "readyReplicas": self.ready_replicas,
            "desiredReplicas": self.desired_replicas,
            "deployedVersion": self.deployed_version,
            "canaryVersion": self.canary_version,
            "conditions": [c.to_dict() for c in self.conditions],
            "lastReconciled": (
                self.last_reconciled.isoformat() if self.last_reconciled else None
            ),
            "failureCount": self.failure_count,
        }


# -- Parsing + validation -----------------------------------------------


class ValidationError(ValueError):
    """Raised when a CR body fails validation."""


def parse_spec(body: Dict[str, Any]) -> ModelDeploymentSpec:
    """Parse a Kubernetes CR `spec` dict into a typed spec."""
    if not isinstance(body, dict):
        raise ValidationError("spec must be an object")

    required = ("modelName", "version", "image")
    for field_name in required:
        if field_name not in body:
            raise ValidationError(f"spec.{field_name} is required")

    name = body["modelName"]
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValidationError(
            f"spec.modelName {name!r} must match RFC 1123 label"
        )

    version = body["version"]
    if not isinstance(version, str) or not version:
        raise ValidationError("spec.version must be a non-empty string")

    replicas = int(body.get("replicas", 2))
    if replicas < 1:
        raise ValidationError("spec.replicas must be >= 1")

    resources_raw = body.get("resources") or {}
    resources = ResourceRequest(
        cpu=str(resources_raw.get("cpu", "500m")),
        memory=str(resources_raw.get("memory", "1Gi")),
        gpu=int(resources_raw.get("gpu", 0)),
    )
    if resources.gpu < 0:
        raise ValidationError("spec.resources.gpu must be >= 0")

    autoscaling_raw = body.get("autoscaling") or {}
    autoscaling = AutoscalingSpec(
        enabled=bool(autoscaling_raw.get("enabled", True)),
        min_replicas=int(autoscaling_raw.get("minReplicas", 1)),
        max_replicas=int(autoscaling_raw.get("maxReplicas", 10)),
        target_cpu_utilization=int(autoscaling_raw.get("targetCpuUtilization", 70)),
        target_queue_depth=(
            int(autoscaling_raw["targetQueueDepth"])
            if "targetQueueDepth" in autoscaling_raw else None
        ),
    )
    if autoscaling.min_replicas > autoscaling.max_replicas:
        raise ValidationError(
            "spec.autoscaling.minReplicas must be <= maxReplicas"
        )

    strategy_raw = body.get("trafficStrategy", TrafficStrategy.BLUE_GREEN.value)
    try:
        strategy = TrafficStrategy(strategy_raw)
    except ValueError as exc:
        raise ValidationError(f"unknown trafficStrategy: {strategy_raw!r}") from exc

    canary_weight = int(body.get("canaryWeightPercent", 0))
    if not 0 <= canary_weight <= 100:
        raise ValidationError("spec.canaryWeightPercent must be in [0, 100]")
    if strategy is TrafficStrategy.CANARY and canary_weight == 0:
        raise ValidationError(
            "Canary trafficStrategy requires canaryWeightPercent > 0"
        )

    return ModelDeploymentSpec(
        model_name=name,
        version=version,
        image=str(body["image"]),
        replicas=replicas,
        resources=resources,
        autoscaling=autoscaling,
        serving_port=int(body.get("servingPort", 8000)),
        health_check_path=str(body.get("healthCheckPath", "/healthz")),
        readiness_check_path=str(body.get("readinessCheckPath", "/ready")),
        traffic_strategy=strategy,
        canary_weight_percent=canary_weight,
        previous_version=body.get("previousVersion"),
        env=dict(body.get("env", {})),
        labels=dict(body.get("labels", {})),
    )


def to_openapi_v3() -> Dict[str, Any]:
    """Return the CRD's OpenAPIV3Schema fragment."""
    return {
        "type": "object",
        "required": ["modelName", "version", "image"],
        "properties": {
            "modelName": {"type": "string", "pattern": "^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$"},
            "version": {"type": "string", "minLength": 1},
            "image": {"type": "string", "minLength": 1},
            "replicas": {"type": "integer", "minimum": 1},
            "servingPort": {"type": "integer", "minimum": 1, "maximum": 65535},
            "healthCheckPath": {"type": "string"},
            "readinessCheckPath": {"type": "string"},
            "trafficStrategy": {
                "type": "string",
                "enum": [s.value for s in TrafficStrategy],
            },
            "canaryWeightPercent": {"type": "integer", "minimum": 0, "maximum": 100},
            "previousVersion": {"type": "string"},
            "resources": {
                "type": "object",
                "properties": {
                    "cpu": {"type": "string"},
                    "memory": {"type": "string"},
                    "gpu": {"type": "integer", "minimum": 0},
                },
            },
            "autoscaling": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "minReplicas": {"type": "integer", "minimum": 1},
                    "maxReplicas": {"type": "integer", "minimum": 1},
                    "targetCpuUtilization": {"type": "integer", "minimum": 1, "maximum": 100},
                    "targetQueueDepth": {"type": "integer", "minimum": 0},
                },
            },
            "env": {"type": "object", "additionalProperties": {"type": "string"}},
            "labels": {"type": "object", "additionalProperties": {"type": "string"}},
        },
    }
