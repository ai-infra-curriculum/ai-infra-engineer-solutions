"""Tests for the cloud-ML infrastructure provisioners."""

import json

import pytest

from src.provisioner import (
    CloudProvider,
    ClusterSize,
    InfrastructurePlan,
    InfrastructureRequest,
    get_provisioner,
)
from src.provisioner.aws_provisioner import AWSProvisioner
from src.provisioner.azure_provisioner import AzureProvisioner
from src.provisioner.gcp_provisioner import GCPProvisioner


@pytest.fixture
def request_dev() -> InfrastructureRequest:
    return InfrastructureRequest(
        project_name="smoke",
        environment="dev",
        region="us-east-1",
        cluster_size=ClusterSize.SMALL,
        tags={"team": "platform"},
    )


@pytest.fixture
def request_prod_gpu() -> InfrastructureRequest:
    return InfrastructureRequest(
        project_name="prod",
        environment="prod",
        region="us-east-1",
        cluster_size=ClusterSize.LARGE,
        enable_gpu=True,
        gpu_count_per_node=4,
        cache_memory_gb=8,
        enable_ha_database=True,
    )


class TestInfrastructureRequest:
    def test_invalid_environment_rejected(self):
        with pytest.raises(ValueError):
            InfrastructureRequest(
                project_name="x",
                environment="staging-2",
                region="us-east-1",
            )

    def test_defaults(self):
        req = InfrastructureRequest(project_name="p", environment="dev", region="us-east-1")
        assert req.cluster_size is ClusterSize.SMALL
        assert req.enable_gpu is False
        assert req.enable_ha_database is True


class TestAWSProvisioner:
    def test_plan_has_all_seven_resource_types(self, request_dev):
        plan = AWSProvisioner().plan(request_dev)
        types = {r.resource_type for r in plan.resources}
        assert types == {
            "vpc",
            "kubernetes_cluster",
            "object_storage",
            "managed_database",
            "managed_cache",
            "load_balancer",
            "monitoring",
        }
        assert plan.provider is CloudProvider.AWS

    def test_kubernetes_uses_eks_instance_type(self, request_dev):
        plan = AWSProvisioner().plan(request_dev)
        k8s = plan.find_resource("kubernetes_cluster")
        assert k8s is not None
        node_pools = k8s.settings["node_pools"]
        assert node_pools[0]["instance_type"] == "m5.xlarge"

    def test_gpu_node_pool_added_when_requested(self, request_prod_gpu):
        plan = AWSProvisioner().plan(request_prod_gpu)
        k8s = plan.find_resource("kubernetes_cluster")
        gpu_pools = [p for p in k8s.settings["node_pools"] if p["name"] == "gpu"]
        assert gpu_pools, "expected a GPU node pool"
        assert gpu_pools[0]["instance_type"] == "p3.2xlarge"

    def test_prod_database_has_multi_az_and_protection(self, request_prod_gpu):
        plan = AWSProvisioner().plan(request_prod_gpu)
        db = plan.find_resource("managed_database")
        assert db.settings["multi_az"] is True
        assert db.settings["deletion_protection"] is True
        assert db.settings["backup_retention_days"] == 7

    def test_dev_database_no_deletion_protection(self, request_dev):
        plan = AWSProvisioner().plan(request_dev)
        db = plan.find_resource("managed_database")
        assert db.settings["deletion_protection"] is False
        assert db.settings["backup_retention_days"] == 1

    def test_cache_warning_for_unusual_size(self):
        req = InfrastructureRequest(
            project_name="x",
            environment="dev",
            region="us-east-1",
            cache_memory_gb=3,
        )
        plan = AWSProvisioner().plan(req)
        assert any("Cache memory" in w for w in plan.warnings)


class TestGCPProvisioner:
    def test_plan_has_all_seven_resource_types(self, request_dev):
        plan = GCPProvisioner().plan(request_dev)
        types = {r.resource_type for r in plan.resources}
        assert "kubernetes_cluster" in types
        assert "managed_database" in types
        assert plan.provider is CloudProvider.GCP

    def test_kubernetes_uses_gke_machine_type(self, request_dev):
        plan = GCPProvisioner().plan(request_dev)
        k8s = plan.find_resource("kubernetes_cluster")
        assert k8s.settings["node_pools"][0]["machine_type"] == "n2-standard-4"

    def test_cloud_sql_uses_regional_for_ha(self, request_prod_gpu):
        plan = GCPProvisioner().plan(request_prod_gpu)
        db = plan.find_resource("managed_database")
        assert db.settings["availability_type"] == "REGIONAL"

    def test_object_storage_lifecycle_present(self, request_dev):
        plan = GCPProvisioner().plan(request_dev)
        storage = plan.find_resource("object_storage")
        rules = storage.settings["lifecycle_rules"]
        assert any(r["storage_class"] == "NEARLINE" for r in rules)
        assert any(r["storage_class"] == "COLDLINE" for r in rules)


class TestAzureProvisioner:
    def test_plan_has_all_seven_resource_types(self, request_dev):
        plan = AzureProvisioner().plan(request_dev)
        types = {r.resource_type for r in plan.resources}
        assert "kubernetes_cluster" in types
        assert "managed_cache" in types

    def test_kubernetes_uses_aks_vm_size(self, request_dev):
        plan = AzureProvisioner().plan(request_dev)
        k8s = plan.find_resource("kubernetes_cluster")
        assert k8s.settings["node_pools"][0]["vm_size"] == "Standard_D4s_v5"

    def test_postgres_zone_redundant_for_ha(self, request_prod_gpu):
        plan = AzureProvisioner().plan(request_prod_gpu)
        db = plan.find_resource("managed_database")
        assert db.settings["high_availability_mode"] == "ZoneRedundant"

    def test_prod_storage_uses_grs(self, request_prod_gpu):
        plan = AzureProvisioner().plan(request_prod_gpu)
        storage = plan.find_resource("object_storage")
        assert storage.settings["account_replication_type"] == "GRS"

    def test_redis_sku_for_premium_memory(self):
        req = InfrastructureRequest(
            project_name="p",
            environment="dev",
            region="eastus",
            cache_memory_gb=16,
        )
        plan = AzureProvisioner().plan(req)
        cache = plan.find_resource("managed_cache")
        assert cache.settings["sku_name"] == "Premium"
        assert cache.settings["family"] == "P"


class TestCrossProvider:
    @pytest.mark.parametrize("provider", list(CloudProvider))
    def test_all_providers_produce_plan_for_dev(self, provider, request_dev):
        cls = get_provisioner(provider)
        plan = cls().plan(request_dev)
        assert isinstance(plan, InfrastructurePlan)
        assert len(plan.resources) == 7

    @pytest.mark.parametrize("provider", list(CloudProvider))
    def test_to_dict_round_trips_through_json(self, provider, request_dev):
        cls = get_provisioner(provider)
        plan = cls().plan(request_dev)
        body = json.dumps(plan.to_dict())
        loaded = json.loads(body)
        assert loaded["provider"] == provider.value
        assert isinstance(loaded["resources"], list)

    def test_cluster_size_propagates_to_node_instance(self):
        large_req = InfrastructureRequest(
            project_name="big",
            environment="prod",
            region="us-east-1",
            cluster_size=ClusterSize.LARGE,
        )
        aws_plan = AWSProvisioner().plan(large_req)
        aws_k8s = aws_plan.find_resource("kubernetes_cluster")
        assert aws_k8s.settings["node_pools"][0]["instance_type"] == "m5.4xlarge"

    def test_get_provisioner_unknown_raises(self):
        with pytest.raises(ValueError):
            get_provisioner("aws")  # type: ignore[arg-type]
