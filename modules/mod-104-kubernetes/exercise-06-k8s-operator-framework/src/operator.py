"""
ModelDeployment Operator

Reconciles ModelDeployment CRs by maintaining a derived set of
Kubernetes resources (Deployment, Service, HPA) consistent with the
declared spec. The operator talks to Kubernetes through a small
KubernetesClient Protocol so tests can inject a deterministic in-memory
implementation; in production the same Protocol is implemented against
the kubernetes-python-client.

The reconciliation loop also handles:
- Auto-rollback when failure_count crosses a threshold and a
  previous_version is recorded.
- Canary-weight tracking when traffic_strategy is Canary.
- Status condition updates so `kubectl describe` shows actionable info.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from .crd import (
    Condition,
    DeploymentPhase,
    ModelDeploymentSpec,
    ModelDeploymentStatus,
    TrafficStrategy,
    parse_spec,
)


logger = logging.getLogger(__name__)


# -- Kubernetes-client abstraction --------------------------------------


@dataclass
class K8sResource:
    """One Kubernetes object owned by the operator."""

    kind: str  # "Deployment", "Service", "HorizontalPodAutoscaler"
    name: str
    namespace: str
    body: Dict[str, Any] = field(default_factory=dict)


class KubernetesClient(Protocol):
    def create_or_update(self, resource: K8sResource) -> K8sResource: ...

    def get(self, kind: str, namespace: str, name: str) -> Optional[K8sResource]: ...

    def delete(self, kind: str, namespace: str, name: str) -> None: ...

    def list(self, kind: str, namespace: str) -> List[K8sResource]: ...

    def deployment_status(self, namespace: str, name: str) -> Dict[str, int]: ...


class InMemoryK8sClient:
    """Reference implementation used in tests + CLI."""

    def __init__(self) -> None:
        self._objects: Dict[Tuple[str, str, str], K8sResource] = {}
        self._status_overrides: Dict[Tuple[str, str], Dict[str, int]] = {}

    def create_or_update(self, resource: K8sResource) -> K8sResource:
        key = (resource.kind, resource.namespace, resource.name)
        self._objects[key] = resource
        return resource

    def get(self, kind: str, namespace: str, name: str) -> Optional[K8sResource]:
        return self._objects.get((kind, namespace, name))

    def delete(self, kind: str, namespace: str, name: str) -> None:
        self._objects.pop((kind, namespace, name), None)

    def list(self, kind: str, namespace: str) -> List[K8sResource]:
        return [
            obj for (k, ns, _), obj in self._objects.items()
            if k == kind and ns == namespace
        ]

    def deployment_status(self, namespace: str, name: str) -> Dict[str, int]:
        key = (namespace, name)
        if key in self._status_overrides:
            return dict(self._status_overrides[key])
        deployment = self._objects.get(("Deployment", namespace, name))
        replicas = (
            deployment.body.get("spec", {}).get("replicas", 0)
            if deployment else 0
        )
        return {"desired_replicas": replicas, "ready_replicas": replicas}

    # -- test helper ---------------------------------------------------

    def set_deployment_status(
        self,
        namespace: str,
        name: str,
        *,
        desired: int,
        ready: int,
    ) -> None:
        self._status_overrides[(namespace, name)] = {
            "desired_replicas": desired,
            "ready_replicas": ready,
        }


# -- Reconciler ----------------------------------------------------------


@dataclass
class ReconcileResult:
    spec: ModelDeploymentSpec
    status: ModelDeploymentStatus
    actions: List[str] = field(default_factory=list)
    triggered_rollback: bool = False


class ModelDeploymentOperator:
    """High-level operator that reconciles a single ModelDeployment CR."""

    FAILURE_THRESHOLD = 3

    def __init__(
        self,
        client: KubernetesClient,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.client = client
        self.clock = clock

    def reconcile(
        self,
        namespace: str,
        name: str,
        spec_body: Dict[str, Any],
        status: Optional[ModelDeploymentStatus] = None,
        *,
        generation: int = 1,
    ) -> ReconcileResult:
        """Bring cluster state in line with the desired spec."""
        spec = parse_spec(spec_body)
        status = status or ModelDeploymentStatus()
        result = ReconcileResult(spec=spec, status=status)
        result.status.observed_generation = generation
        result.status.last_reconciled = self.clock()
        result.status.desired_replicas = spec.replicas

        # Rollback decision before pushing new resources.
        if self._should_rollback(status, spec):
            result.triggered_rollback = True
            spec.version, spec.previous_version = spec.previous_version, spec.version
            result.actions.append(f"Rolling back to previous version {spec.version}")
            result.status.phase = DeploymentPhase.ROLLED_BACK
            result.status.failure_count = 0
            result.status.set_condition(Condition(
                type="Rolledback",
                status="True",
                reason="FailureThresholdExceeded",
                message=f"Rolled back from version {spec.previous_version}",
                last_transition_time=self.clock(),
            ))

        # Always (re)apply derived resources.
        self._apply_deployment(namespace, name, spec)
        result.actions.append("Applied Deployment")
        self._apply_service(namespace, name, spec)
        result.actions.append("Applied Service")
        if spec.autoscaling.enabled:
            self._apply_hpa(namespace, name, spec)
            result.actions.append("Applied HorizontalPodAutoscaler")
        else:
            self.client.delete("HorizontalPodAutoscaler", namespace, name)

        # Probe live state to update status.
        deployment_status = self.client.deployment_status(namespace, name)
        ready = deployment_status.get("ready_replicas", 0)
        result.status.ready_replicas = ready
        result.status.deployed_version = spec.version
        result.status.canary_version = (
            spec.version if spec.traffic_strategy is TrafficStrategy.CANARY else None
        )

        if result.triggered_rollback:
            pass  # phase already set above
        elif ready >= spec.replicas:
            result.status.phase = DeploymentPhase.READY
            result.status.failure_count = 0
            result.status.set_condition(Condition(
                type="Ready", status="True",
                reason="AllReplicasReady",
                message=f"{ready}/{spec.replicas} replicas ready",
                last_transition_time=self.clock(),
            ))
        elif ready == 0:
            result.status.phase = DeploymentPhase.FAILED
            result.status.failure_count += 1
            result.status.set_condition(Condition(
                type="Ready", status="False",
                reason="NoReadyReplicas",
                message="0 replicas ready",
                last_transition_time=self.clock(),
            ))
        else:
            result.status.phase = DeploymentPhase.DEGRADED
            result.status.failure_count = 0
            result.status.set_condition(Condition(
                type="Ready", status="False",
                reason="PartiallyReady",
                message=f"{ready}/{spec.replicas} replicas ready",
                last_transition_time=self.clock(),
            ))

        return result

    def delete(self, namespace: str, name: str) -> List[str]:
        """Tear down derived resources when the CR is deleted."""
        actions: List[str] = []
        for kind in ("HorizontalPodAutoscaler", "Service", "Deployment"):
            self.client.delete(kind, namespace, name)
            actions.append(f"Deleted {kind} {namespace}/{name}")
        return actions

    # -- internals -----------------------------------------------------

    def _should_rollback(
        self,
        status: ModelDeploymentStatus,
        spec: ModelDeploymentSpec,
    ) -> bool:
        return (
            spec.previous_version is not None
            and status.failure_count >= self.FAILURE_THRESHOLD
        )

    def _apply_deployment(self, namespace: str, name: str, spec: ModelDeploymentSpec) -> None:
        resources_block = {
            "limits": {
                "cpu": spec.resources.cpu,
                "memory": spec.resources.memory,
                **({"nvidia.com/gpu": str(spec.resources.gpu)} if spec.resources.gpu else {}),
            },
            "requests": {
                "cpu": spec.resources.cpu,
                "memory": spec.resources.memory,
            },
        }
        labels = {"app": name, "version": spec.version, **spec.labels}
        body = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "replicas": spec.replicas,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "containers": [{
                            "name": "model",
                            "image": spec.image,
                            "ports": [{"containerPort": spec.serving_port}],
                            "env": [{"name": k, "value": v} for k, v in spec.env.items()],
                            "resources": resources_block,
                            "livenessProbe": {
                                "httpGet": {"path": spec.health_check_path, "port": spec.serving_port},
                            },
                            "readinessProbe": {
                                "httpGet": {"path": spec.readiness_check_path, "port": spec.serving_port},
                            },
                        }],
                    },
                },
            },
        }
        self.client.create_or_update(K8sResource(
            kind="Deployment", name=name, namespace=namespace, body=body,
        ))

    def _apply_service(self, namespace: str, name: str, spec: ModelDeploymentSpec) -> None:
        body = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "selector": {"app": name},
                "ports": [{"port": 80, "targetPort": spec.serving_port}],
                "type": "ClusterIP",
            },
        }
        self.client.create_or_update(K8sResource(
            kind="Service", name=name, namespace=namespace, body=body,
        ))

    def _apply_hpa(self, namespace: str, name: str, spec: ModelDeploymentSpec) -> None:
        body = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": name,
                },
                "minReplicas": spec.autoscaling.min_replicas,
                "maxReplicas": spec.autoscaling.max_replicas,
                "metrics": [{
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": spec.autoscaling.target_cpu_utilization,
                        },
                    },
                }],
            },
        }
        self.client.create_or_update(K8sResource(
            kind="HorizontalPodAutoscaler", name=name, namespace=namespace, body=body,
        ))
