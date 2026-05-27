"""Tests for the Pulumi-style multi-cloud infrastructure builder."""

import json

import pytest

from src.infrastructure import (
    AwsEKS,
    AwsStorage,
    AzureMonitor,
    AzureMonitorConfig,
    EksConfig,
    GcpTpu,
    MultiCloudMLPlatform,
    Provider,
    Resource,
    ResourceID,
    Stack,
    StorageConfig,
    TpuConfig,
    diff_stacks,
    estimate_cost,
)


@pytest.fixture
def platform():
    return MultiCloudMLPlatform(project_name="ml-platform", stack_name="dev")


class TestStackBasics:
    def test_resource_added_to_stack(self):
        stack = Stack(name="test")
        resource = Resource(
            id=ResourceID(Provider.AWS, "aws:s3:Bucket", "b1"),
            properties={"bucket": "b1"},
        )
        stack.add(resource)
        assert stack.find("b1") is resource

    def test_output_added_to_stack(self):
        stack = Stack(name="test")
        stack.output("name", "value", sensitive=True)
        assert len(stack.outputs) == 1
        assert stack.outputs[0].sensitive

    def test_to_dict_includes_fingerprints(self):
        stack = Stack(name="test")
        stack.add(Resource(
            id=ResourceID(Provider.AWS, "aws:s3:Bucket", "b1"),
            properties={"bucket": "b1"},
        ))
        payload = stack.to_dict()
        assert "fingerprint" in payload["resources"][0]
        assert payload["resources"][0]["urn"].startswith("urn:pulumi:test::aws::aws:s3:Bucket::b1")


class TestAwsStorage:
    def test_creates_bucket_resource(self):
        stack = Stack(name="dev")
        AwsStorage("models", StorageConfig(bucket_name="ml-platform-models")).register(stack)
        bucket = stack.find("ml-platform-models")
        assert bucket is not None
        assert bucket.properties["versioning"]["enabled"]

    def test_lifecycle_rule_when_configured(self):
        stack = Stack(name="dev")
        AwsStorage("models", StorageConfig(
            bucket_name="m", lifecycle_to_ia_days=45,
        )).register(stack)
        bucket = stack.find("m")
        transitions = bucket.properties["lifecycleRules"][0]["transitions"]
        assert transitions[0]["days"] == 45

    def test_lifecycle_skipped_when_none(self):
        stack = Stack(name="dev")
        AwsStorage("models", StorageConfig(
            bucket_name="m", lifecycle_to_ia_days=None,
        )).register(stack)
        bucket = stack.find("m")
        assert bucket.properties["lifecycleRules"][0]["transitions"] == []


class TestGcpTpu:
    def test_tpu_properties(self):
        stack = Stack(name="dev")
        GcpTpu(
            "tpu-1", TpuConfig(accelerator_type="v4-8", preemptible=True),
            project="my-project", zone="us-central1-a",
        ).register(stack)
        tpu = stack.find("tpu-1")
        assert tpu.properties["acceleratorType"] == "v4-8"
        assert tpu.properties["schedulingConfig"]["preemptible"]


class TestAwsEKS:
    def test_creates_full_cluster_stack(self):
        stack = Stack(name="dev")
        AwsEKS("eks", EksConfig(cluster_name="ml-eks", region="us-east-1")).register(stack)
        types = {r.id.resource_type for r in stack.resources}
        assert "aws:iam:Role" in types
        assert "aws:eks:Cluster" in types
        assert "aws:eks:NodeGroup" in types

    def test_node_group_dependencies(self):
        stack = Stack(name="dev")
        AwsEKS("eks", EksConfig(cluster_name="c", region="us-east-1")).register(stack)
        node_group = next(
            r for r in stack.resources if r.id.resource_type == "aws:eks:NodeGroup"
        )
        cluster = next(
            r for r in stack.resources if r.id.resource_type == "aws:eks:Cluster"
        )
        node_role = next(
            r for r in stack.resources
            if r.id.resource_type == "aws:iam:Role" and "node-role" in r.id.logical_name
        )
        deps = set(node_group.dependencies)
        assert cluster.id.urn(stack.name) in deps
        assert node_role.id.urn(stack.name) in deps


class TestAzureMonitor:
    def test_workspace_only_when_alerts_disabled(self):
        stack = Stack(name="dev")
        AzureMonitor(
            "mon",
            AzureMonitorConfig(workspace_name="ws", enable_alerts=False),
            resource_group="rg",
        ).register(stack)
        types = [r.id.resource_type for r in stack.resources]
        assert types == ["azure:operationalinsights:Workspace"]

    def test_alert_added_when_enabled(self):
        stack = Stack(name="dev")
        AzureMonitor(
            "mon",
            AzureMonitorConfig(workspace_name="ws", enable_alerts=True),
            resource_group="rg",
        ).register(stack)
        types = [r.id.resource_type for r in stack.resources]
        assert "azure:insights:MetricAlert" in types


class TestMultiCloudPlatform:
    def test_full_stack_includes_all_providers(self, platform):
        stack = platform.build()
        providers = {r.id.provider for r in stack.resources}
        assert providers == {Provider.AWS, Provider.GCP, Provider.AZURE}

    def test_outputs_include_models_bucket_and_eks(self, platform):
        stack = platform.build()
        names = {o.name for o in stack.outputs}
        assert "models_bucket" in names
        assert "eks_cluster_name" in names

    def test_tpu_excluded_when_disabled(self, platform):
        stack = platform.build(include_tpu=False)
        gcp_resources = [r for r in stack.resources if r.id.provider is Provider.GCP]
        assert not gcp_resources

    def test_common_tags_propagate_to_all_resources(self, platform):
        stack = platform.build()
        for r in stack.resources:
            assert r.tags.get("Project") == "ml-platform"
            assert r.tags.get("ManagedBy") == "pulumi"


class TestStackDiff:
    def test_create_when_resource_only_in_current(self, platform):
        previous = platform.build(include_tpu=False)
        current = platform.build(include_tpu=True)
        delta = diff_stacks(previous, current)
        assert delta.to_create
        assert all(d.urn for d in delta.to_create)

    def test_delete_when_resource_removed(self, platform):
        previous = platform.build(include_tpu=True)
        current = platform.build(include_tpu=False)
        delta = diff_stacks(previous, current)
        assert delta.to_delete
        deleted_types = [d.urn.split("::")[-2] for d in delta.to_delete]
        assert any("tpu" in t for t in deleted_types)

    def test_update_on_property_change(self, platform):
        previous = platform.build()
        # Build again with a different stack name change (force a property
        # difference via the platform's TPU preemptibility flag → switch
        # stack name to 'prod' so preemptible flips False).
        prod_platform = MultiCloudMLPlatform(
            project_name="ml-platform", stack_name="dev",
        )
        # Forge an updated resource fingerprint by mutating one property.
        current = platform.build()
        # Find an arbitrary resource and tweak its property.
        target = current.find("ml-platform-dev-models")
        target.properties["versioning"] = {"enabled": False}
        delta = diff_stacks(previous, current)
        assert delta.to_update
        target_urn = target.id.urn(current.name)
        assert any(d.urn == target_urn for d in delta.to_update)

    def test_no_diff_for_identical_stacks(self, platform):
        a = platform.build()
        b = platform.build()
        delta = diff_stacks(a, b)
        assert not delta.diffs

    def test_stacks_with_different_names_rejected(self, platform):
        a = platform.build()
        b = Stack(name="other")
        with pytest.raises(ValueError):
            diff_stacks(a, b)


class TestCostEstimator:
    def test_cost_includes_all_categories(self, platform):
        stack = platform.build()
        breakdown = estimate_cost(stack)
        assert breakdown.aws_compute_usd > 0
        assert breakdown.aws_storage_usd > 0
        assert breakdown.gcp_tpu_usd > 0
        assert breakdown.azure_monitor_usd > 0

    def test_preemptible_tpu_cheaper(self):
        regular = MultiCloudMLPlatform(project_name="p", stack_name="prod").build()
        preemptible = MultiCloudMLPlatform(project_name="p", stack_name="dev").build()
        reg = estimate_cost(regular).gcp_tpu_usd
        preempt = estimate_cost(preemptible).gcp_tpu_usd
        assert preempt < reg

    def test_no_tpu_zero_gcp_cost(self):
        stack = MultiCloudMLPlatform(project_name="p", stack_name="dev").build(include_tpu=False)
        breakdown = estimate_cost(stack)
        assert breakdown.gcp_tpu_usd == 0.0


class TestStackSerialization:
    def test_to_dict_includes_resources_and_outputs(self, platform):
        stack = platform.build()
        payload = stack.to_dict()
        assert "resources" in payload and "outputs" in payload
        assert len(payload["resources"]) == len(stack.resources)
        # JSON-serializable.
        json.dumps(payload, default=str)
