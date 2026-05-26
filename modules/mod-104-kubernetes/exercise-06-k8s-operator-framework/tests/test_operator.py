"""Tests for the ModelDeployment CRD parser + Operator."""

from datetime import datetime, timezone

import pytest

from src.crd import (
    AutoscalingSpec,
    Condition,
    DeploymentPhase,
    ModelDeploymentSpec,
    ModelDeploymentStatus,
    ResourceRequest,
    TrafficStrategy,
    ValidationError,
    parse_spec,
    to_openapi_v3,
)
from src.operator import (
    InMemoryK8sClient,
    K8sResource,
    ModelDeploymentOperator,
)


BASE_SPEC = {
    "modelName": "fraud-classifier",
    "version": "v2.3.1",
    "image": "registry.example.com/fraud:v2.3.1",
    "replicas": 3,
    "resources": {"cpu": "1", "memory": "2Gi"},
}


class TestCRDParser:
    def test_minimum_spec_parses(self):
        spec = parse_spec({
            "modelName": "img-classifier",
            "version": "v1.0.0",
            "image": "registry/img:v1",
        })
        assert spec.model_name == "img-classifier"
        assert spec.replicas == 2  # default

    def test_full_spec_parses(self):
        spec = parse_spec({
            **BASE_SPEC,
            "autoscaling": {
                "enabled": True,
                "minReplicas": 2,
                "maxReplicas": 12,
                "targetCpuUtilization": 60,
                "targetQueueDepth": 10,
            },
            "trafficStrategy": "Canary",
            "canaryWeightPercent": 10,
            "previousVersion": "v2.3.0",
            "env": {"FOO": "bar"},
            "labels": {"team": "ml"},
        })
        assert spec.autoscaling.max_replicas == 12
        assert spec.autoscaling.target_queue_depth == 10
        assert spec.traffic_strategy is TrafficStrategy.CANARY
        assert spec.canary_weight_percent == 10
        assert spec.env == {"FOO": "bar"}

    @pytest.mark.parametrize("field_name", ["modelName", "version", "image"])
    def test_required_fields(self, field_name: str):
        body = dict(BASE_SPEC)
        del body[field_name]
        with pytest.raises(ValidationError):
            parse_spec(body)

    def test_invalid_model_name(self):
        with pytest.raises(ValidationError):
            parse_spec({**BASE_SPEC, "modelName": "Invalid_Name"})

    def test_zero_replicas_rejected(self):
        with pytest.raises(ValidationError):
            parse_spec({**BASE_SPEC, "replicas": 0})

    def test_canary_requires_weight(self):
        with pytest.raises(ValidationError):
            parse_spec({**BASE_SPEC, "trafficStrategy": "Canary", "canaryWeightPercent": 0})

    def test_autoscaling_min_gt_max_rejected(self):
        with pytest.raises(ValidationError):
            parse_spec({
                **BASE_SPEC,
                "autoscaling": {"minReplicas": 10, "maxReplicas": 5},
            })

    def test_openapi_v3_has_required_fields(self):
        schema = to_openapi_v3()
        assert schema["required"] == ["modelName", "version", "image"]
        assert "trafficStrategy" in schema["properties"]


class TestStatus:
    def test_set_condition_replaces_existing(self):
        status = ModelDeploymentStatus()
        status.set_condition(Condition(type="Ready", status="False"))
        status.set_condition(Condition(type="Ready", status="True"))
        types = [c.type for c in status.conditions]
        assert types == ["Ready"]
        assert status.conditions[0].status == "True"

    def test_to_dict_serializes(self):
        status = ModelDeploymentStatus(
            phase=DeploymentPhase.READY,
            ready_replicas=3,
            desired_replicas=3,
            deployed_version="v1.0.0",
        )
        data = status.to_dict()
        assert data["phase"] == "Ready"
        assert data["readyReplicas"] == 3


class TestOperatorReconciliation:
    def _client(self) -> InMemoryK8sClient:
        return InMemoryK8sClient()

    def test_creates_deployment_service_hpa(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        result = op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        assert client.get("Deployment", "ml", "fraud-classifier") is not None
        assert client.get("Service", "ml", "fraud-classifier") is not None
        assert client.get("HorizontalPodAutoscaler", "ml", "fraud-classifier") is not None
        assert "Applied Deployment" in result.actions

    def test_hpa_skipped_when_autoscaling_disabled(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        spec_body = {**BASE_SPEC, "autoscaling": {"enabled": False}}
        op.reconcile("ml", "fraud-classifier", spec_body)
        assert client.get("HorizontalPodAutoscaler", "ml", "fraud-classifier") is None

    def test_deployment_body_includes_resources_and_probes(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        deployment = client.get("Deployment", "ml", "fraud-classifier")
        container = deployment.body["spec"]["template"]["spec"]["containers"][0]
        assert container["resources"]["limits"]["cpu"] == "1"
        assert "livenessProbe" in container
        assert "readinessProbe" in container

    def test_status_transitions_to_ready_when_replicas_ready(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        result = op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        assert result.status.phase is DeploymentPhase.READY
        assert result.status.ready_replicas == 3

    def test_status_transitions_to_degraded_on_partial_readiness(self):
        client = self._client()
        # Create the deployment via reconcile, then override ready count.
        op = ModelDeploymentOperator(client)
        op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        client.set_deployment_status("ml", "fraud-classifier", desired=3, ready=1)
        result = op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        assert result.status.phase is DeploymentPhase.DEGRADED
        assert any(c.type == "Ready" and c.status == "False" for c in result.status.conditions)

    def test_status_failed_when_no_replicas_ready(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        client.set_deployment_status("ml", "fraud-classifier", desired=3, ready=0)
        result = op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        assert result.status.phase is DeploymentPhase.FAILED
        assert result.status.failure_count == 1

    def test_auto_rollback_after_threshold(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        spec_body = {**BASE_SPEC, "previousVersion": "v2.2.0"}
        pre = ModelDeploymentStatus(failure_count=3)
        client.set_deployment_status("ml", "fraud-classifier", desired=3, ready=0)
        result = op.reconcile("ml", "fraud-classifier", spec_body, status=pre)
        assert result.triggered_rollback
        # Spec version has swapped to the previous one.
        assert result.spec.version == "v2.2.0"
        assert result.status.phase is DeploymentPhase.ROLLED_BACK

    def test_canary_version_recorded_for_canary_strategy(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        spec_body = {
            **BASE_SPEC,
            "trafficStrategy": "Canary",
            "canaryWeightPercent": 10,
        }
        result = op.reconcile("ml", "fraud-classifier", spec_body)
        assert result.status.canary_version == "v2.3.1"

    def test_delete_removes_all_resources(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        actions = op.delete("ml", "fraud-classifier")
        assert client.get("Deployment", "ml", "fraud-classifier") is None
        assert client.get("Service", "ml", "fraud-classifier") is None
        assert len(actions) == 3

    def test_reconcile_is_idempotent(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        first = client.get("Deployment", "ml", "fraud-classifier").body
        op.reconcile("ml", "fraud-classifier", BASE_SPEC)
        second = client.get("Deployment", "ml", "fraud-classifier").body
        assert first == second

    def test_observed_generation_tracks_input(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        result = op.reconcile("ml", "fraud-classifier", BASE_SPEC, generation=7)
        assert result.status.observed_generation == 7

    def test_gpu_request_propagated(self):
        client = self._client()
        op = ModelDeploymentOperator(client)
        spec_body = {**BASE_SPEC, "resources": {"cpu": "2", "memory": "8Gi", "gpu": 1}}
        op.reconcile("ml", "fraud-classifier", spec_body)
        container = client.get("Deployment", "ml", "fraud-classifier") \
            .body["spec"]["template"]["spec"]["containers"][0]
        assert container["resources"]["limits"]["nvidia.com/gpu"] == "1"
