"""
Azure Provisioner

Produces an Azure-flavored InfrastructurePlan: AKS for Kubernetes, Blob
Storage container, Azure Database for PostgreSQL, Azure Cache for
Redis, Application Gateway for load balancing, a Virtual Network with
subnets, and a Prometheus/Grafana Helm deployment plus Azure Monitor
integration.
"""

from __future__ import annotations

import logging
from typing import Dict

from . import (
    CLUSTER_SIZE_DEFAULTS,
    CloudProvider,
    ClusterSize,
    InfrastructurePlan,
    InfrastructureRequest,
    ResourcePlan,
)

logger = logging.getLogger(__name__)


_AZURE_NODE_VM_SIZES: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "Standard_D4s_v5",
    ClusterSize.MEDIUM: "Standard_D8s_v5",
    ClusterSize.LARGE: "Standard_D16s_v5",
}

_AZURE_GPU_VM_SIZES: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "Standard_NC4as_T4_v3",
    ClusterSize.MEDIUM: "Standard_NC6s_v3",
    ClusterSize.LARGE: "Standard_NC24ads_A100_v4",
}

_AZURE_POSTGRES_SKUS: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "Standard_D2ds_v4",  # General purpose, 2 vCore
    ClusterSize.MEDIUM: "Standard_D4ds_v4",  # 4 vCore
    ClusterSize.LARGE: "Standard_D8ds_v4",  # 8 vCore
}

_AZURE_REDIS_SKUS: Dict[int, Dict[str, object]] = {
    2: {"family": "C", "sku": "Standard", "capacity": 1},
    4: {"family": "C", "sku": "Standard", "capacity": 2},
    8: {"family": "C", "sku": "Standard", "capacity": 3},
    16: {"family": "P", "sku": "Premium", "capacity": 1},
    32: {"family": "P", "sku": "Premium", "capacity": 2},
}


class AzureProvisioner:
    """Build an Azure deployment plan."""

    PROVIDER = CloudProvider.AZURE

    def plan(self, request: InfrastructureRequest) -> InfrastructurePlan:
        plan = InfrastructurePlan(provider=self.PROVIDER, request=request)
        self._add_networking(plan)
        self._add_kubernetes(plan)
        self._add_object_storage(plan)
        self._add_database(plan)
        self._add_cache(plan)
        self._add_load_balancer(plan)
        self._add_monitoring(plan)
        return plan

    def _name(self, request: InfrastructureRequest, suffix: str) -> str:
        # Azure resource names cap at 63 chars and disallow some chars;
        # the simple convention here stays well within constraints.
        return f"{request.project_name}-{request.environment}-{suffix}".lower()

    def _tags(self, request: InfrastructureRequest) -> Dict[str, str]:
        return {
            "Project": request.project_name,
            "Environment": request.environment,
            "ManagedBy": "ml-infrastructure-provisioner",
            **request.tags,
        }

    def _add_networking(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="vpc",
            name=self._name(request, "vnet"),
            provider=self.PROVIDER,
            settings={
                "address_space": ["10.0.0.0/16"],
                "subnets": [
                    {"name": "aks", "cidr": "10.0.0.0/20"},
                    {"name": "data", "cidr": "10.0.16.0/24"},
                    {"name": "lb", "cidr": "10.0.17.0/24"},
                ],
                "ddos_protection": request.environment == "prod",
                "tags": self._tags(request),
            },
        ))

    def _add_kubernetes(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        size_cfg = CLUSTER_SIZE_DEFAULTS[request.cluster_size]
        node_pools = [{
            "name": "default",
            "vm_size": _AZURE_NODE_VM_SIZES[request.cluster_size],
            "min_count": size_cfg["min_nodes"],
            "max_count": size_cfg["max_nodes"],
            "node_count": size_cfg["min_nodes"],
            "node_labels": {"workload": "general"},
        }]
        if request.enable_gpu:
            node_pools.append({
                "name": "gpu",
                "vm_size": _AZURE_GPU_VM_SIZES[request.cluster_size],
                "min_count": 0,
                "max_count": max(2, request.gpu_count_per_node or 2),
                "node_count": 0,
                "node_labels": {"workload": "gpu"},
                "node_taints": ["nvidia.com/gpu=true:NoSchedule"],
            })
        plan.resources.append(ResourcePlan(
            resource_type="kubernetes_cluster",
            name=self._name(request, "aks"),
            provider=self.PROVIDER,
            settings={
                "kubernetes_version": "1.29",
                "private_cluster_enabled": True,
                "azure_policy_enabled": True,
                "node_pools": node_pools,
                "network_plugin": "azure",
                "network_policy": "calico",
                "tags": self._tags(request),
            },
        ))

    def _add_object_storage(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="object_storage",
            name=self._name(request, "blob"),
            provider=self.PROVIDER,
            settings={
                "service": "BlobStorage",
                "account_tier": "Standard",
                "account_replication_type": "GRS" if request.environment == "prod" else "LRS",
                "min_tls_version": "TLS1_2",
                "enable_versioning": request.storage_versioning,
                "lifecycle_rules": [
                    {"days_after_modification": 30, "tier": "Cool"},
                    {"days_after_modification": 90, "tier": "Archive"},
                ],
                "tags": self._tags(request),
            },
        ))

    def _add_database(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="managed_database",
            name=self._name(request, "postgres"),
            provider=self.PROVIDER,
            settings={
                "service": "AzureDatabaseForPostgreSQL",
                "version": "15",
                "sku_name": _AZURE_POSTGRES_SKUS[request.cluster_size],
                "storage_mb": request.database_storage_gb * 1024,
                "high_availability_mode": "ZoneRedundant" if request.enable_ha_database else "Disabled",
                "backup_retention_days": 7 if request.environment == "prod" else 1,
                "geo_redundant_backup_enabled": request.environment == "prod",
                "tags": self._tags(request),
            },
        ))

    def _add_cache(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        sku = _AZURE_REDIS_SKUS.get(request.cache_memory_gb, _AZURE_REDIS_SKUS[2])
        if request.cache_memory_gb not in _AZURE_REDIS_SKUS:
            plan.warnings.append(
                f"Cache memory {request.cache_memory_gb}GB has no exact Azure match; "
                f"rounded to family={sku['family']} sku={sku['sku']} capacity={sku['capacity']}."
            )
        plan.resources.append(ResourcePlan(
            resource_type="managed_cache",
            name=self._name(request, "redis"),
            provider=self.PROVIDER,
            settings={
                "service": "AzureCacheForRedis",
                "family": sku["family"],
                "sku_name": sku["sku"],
                "capacity": sku["capacity"],
                "enable_non_ssl_port": False,
                "minimum_tls_version": "1.2",
                "tags": self._tags(request),
            },
        ))

    def _add_load_balancer(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="load_balancer",
            name=self._name(request, "appgw"),
            provider=self.PROVIDER,
            settings={
                "service": "ApplicationGateway",
                "sku": "WAF_v2",
                "min_capacity": 2,
                "max_capacity": 10,
                "ssl_policy": {"policy_type": "Predefined", "policy_name": "AppGwSslPolicy20220101S"},
                "tags": self._tags(request),
            },
        ))

    def _add_monitoring(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="monitoring",
            name=self._name(request, "monitoring"),
            provider=self.PROVIDER,
            settings={
                "prometheus_helm_chart": "kube-prometheus-stack",
                "prometheus_version": "55.5.0",
                "grafana_admin_user_secret": "grafana-admin",
                "azure_monitor_integration": True,
                "log_analytics_workspace_enabled": True,
                "alerting_targets": ["pagerduty", "slack"],
                "retention_days": 30 if request.environment == "prod" else 7,
            },
        ))
