"""
GCP Provisioner

Produces a GCP-flavored InfrastructurePlan: GKE for Kubernetes, Cloud
Storage bucket, Cloud SQL Postgres, Memorystore Redis, Cloud Load
Balancer, a VPC with subnets, and a Prometheus/Grafana Helm deployment.
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


_GCP_NODE_MACHINE_TYPES: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "n2-standard-4",
    ClusterSize.MEDIUM: "n2-standard-8",
    ClusterSize.LARGE: "n2-standard-16",
}

_GCP_GPU_MACHINE_TYPES: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "n1-standard-4-t4",
    ClusterSize.MEDIUM: "n1-standard-8-v100",
    ClusterSize.LARGE: "a2-highgpu-1g",
}

_GCP_CLOUD_SQL_TIERS: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "db-custom-2-7680",  # 2 vCPU, 7.5GB
    ClusterSize.MEDIUM: "db-custom-4-15360",  # 4 vCPU, 15GB
    ClusterSize.LARGE: "db-custom-8-30720",  # 8 vCPU, 30GB
}

_GCP_MEMORYSTORE_TIERS: Dict[int, str] = {
    2: "BASIC",
    4: "BASIC",
    8: "STANDARD_HA",
    16: "STANDARD_HA",
    32: "STANDARD_HA",
}


class GCPProvisioner:
    """Build a GCP deployment plan."""

    PROVIDER = CloudProvider.GCP

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
        return f"{request.project_name}-{request.environment}-{suffix}".lower()

    def _labels(self, request: InfrastructureRequest) -> Dict[str, str]:
        return {
            "project": request.project_name,
            "environment": request.environment,
            "managed_by": "ml-infrastructure-provisioner",
            **{k.lower(): v.lower() for k, v in request.tags.items()},
        }

    def _add_networking(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="vpc",
            name=self._name(request, "network"),
            provider=self.PROVIDER,
            settings={
                "subnets": [
                    {"region": request.region, "cidr": "10.0.0.0/20", "name": "primary"},
                ],
                "secondary_ip_ranges": [
                    {"name": "pods", "cidr": "10.10.0.0/16"},
                    {"name": "services", "cidr": "10.20.0.0/16"},
                ],
                "enable_private_google_access": True,
                "labels": self._labels(request),
            },
        ))

    def _add_kubernetes(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        size_cfg = CLUSTER_SIZE_DEFAULTS[request.cluster_size]
        node_pools = [{
            "name": "default",
            "machine_type": _GCP_NODE_MACHINE_TYPES[request.cluster_size],
            "min_count": size_cfg["min_nodes"],
            "max_count": size_cfg["max_nodes"],
            "initial_count": size_cfg["min_nodes"],
            "labels": {"workload": "general"},
        }]
        if request.enable_gpu:
            node_pools.append({
                "name": "gpu",
                "machine_type": _GCP_GPU_MACHINE_TYPES[request.cluster_size],
                "min_count": 0,
                "max_count": max(2, request.gpu_count_per_node or 2),
                "initial_count": 0,
                "labels": {"workload": "gpu"},
                "taints": [{"key": "nvidia.com/gpu", "value": "true", "effect": "NO_SCHEDULE"}],
            })
        plan.resources.append(ResourcePlan(
            resource_type="kubernetes_cluster",
            name=self._name(request, "gke"),
            provider=self.PROVIDER,
            settings={
                "k8s_version": "1.29",
                "release_channel": "REGULAR",
                "private_cluster": True,
                "node_pools": node_pools,
                "workload_identity": True,
                "labels": self._labels(request),
            },
        ))

    def _add_object_storage(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="object_storage",
            name=self._name(request, "models"),
            provider=self.PROVIDER,
            settings={
                "service": "CloudStorage",
                "storage_class": "STANDARD",
                "versioning": request.storage_versioning,
                "uniform_bucket_level_access": True,
                "encryption_default_kms_key": None,
                "lifecycle_rules": [
                    {"action": "SetStorageClass", "storage_class": "NEARLINE", "age_days": 30},
                    {"action": "SetStorageClass", "storage_class": "COLDLINE", "age_days": 90},
                ],
                "labels": self._labels(request),
            },
        ))

    def _add_database(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="managed_database",
            name=self._name(request, "postgres"),
            provider=self.PROVIDER,
            settings={
                "service": "CloudSQL",
                "engine": "POSTGRES_15",
                "tier": _GCP_CLOUD_SQL_TIERS[request.cluster_size],
                "disk_size_gb": request.database_storage_gb,
                "availability_type": "REGIONAL" if request.enable_ha_database else "ZONAL",
                "backup_enabled": True,
                "point_in_time_recovery": request.environment == "prod",
                "deletion_protection": request.environment == "prod",
                "labels": self._labels(request),
            },
        ))

    def _add_cache(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        tier = _GCP_MEMORYSTORE_TIERS.get(request.cache_memory_gb, "STANDARD_HA")
        if request.cache_memory_gb not in _GCP_MEMORYSTORE_TIERS:
            plan.warnings.append(
                f"Cache memory {request.cache_memory_gb}GB rounded to GCP tier {tier}."
            )
        plan.resources.append(ResourcePlan(
            resource_type="managed_cache",
            name=self._name(request, "redis"),
            provider=self.PROVIDER,
            settings={
                "service": "Memorystore",
                "engine": "redis_7_0",
                "tier": tier,
                "memory_size_gb": request.cache_memory_gb,
                "transit_encryption_mode": "SERVER_AUTHENTICATION",
                "labels": self._labels(request),
            },
        ))

    def _add_load_balancer(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="load_balancer",
            name=self._name(request, "lb"),
            provider=self.PROVIDER,
            settings={
                "service": "GlobalHTTPSLoadBalancer",
                "ssl_policy": "MODERN",
                "ssl_min_tls_version": "TLS_1_2",
                "labels": self._labels(request),
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
                "cloud_monitoring_integration": True,
                "cloud_logging_integration": True,
                "alerting_targets": ["pagerduty", "slack"],
                "retention_days": 30 if request.environment == "prod" else 7,
            },
        ))
