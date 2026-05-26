"""
AWS Provisioner

Translates a portable InfrastructureRequest into an AWS-flavored
InfrastructurePlan: EKS for Kubernetes, S3 for object storage, RDS for
the managed Postgres tier, ElastiCache for Redis, an ALB for load
balancing, a VPC with public/private subnets, and a Prometheus/Grafana
Helm-chart deployment for monitoring.

The provisioner does not call AWS — it produces a deterministic plan
that the caller submits to Terraform / CloudFormation / boto3.
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


# AWS instance-type catalog keyed by portable size. Values are
# representative compute-optimized choices for ML serving workloads.
_AWS_NODE_INSTANCE_TYPES: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "m5.xlarge",
    ClusterSize.MEDIUM: "m5.2xlarge",
    ClusterSize.LARGE: "m5.4xlarge",
}

_AWS_GPU_NODE_INSTANCE_TYPES: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "g4dn.xlarge",
    ClusterSize.MEDIUM: "g4dn.2xlarge",
    ClusterSize.LARGE: "p3.2xlarge",
}

_AWS_RDS_INSTANCE_CLASSES: Dict[ClusterSize, str] = {
    ClusterSize.SMALL: "db.t3.medium",
    ClusterSize.MEDIUM: "db.m5.large",
    ClusterSize.LARGE: "db.m5.2xlarge",
}

_AWS_ELASTICACHE_NODE_TYPES: Dict[int, str] = {
    2: "cache.t3.micro",
    4: "cache.t3.small",
    8: "cache.t3.medium",
    16: "cache.m5.large",
    32: "cache.m5.xlarge",
}


class AWSProvisioner:
    """Build an AWS deployment plan."""

    PROVIDER = CloudProvider.AWS

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

    # -- individual resources ------------------------------------------

    def _name(self, request: InfrastructureRequest, suffix: str) -> str:
        return f"{request.project_name}-{request.environment}-{suffix}".lower()

    def _common_tags(self, request: InfrastructureRequest) -> Dict[str, str]:
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
            name=self._name(request, "vpc"),
            provider=self.PROVIDER,
            settings={
                "cidr_block": "10.0.0.0/16",
                "public_subnets": ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"],
                "private_subnets": ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"],
                "availability_zones": [f"{request.region}{az}" for az in ("a", "b", "c")],
                "enable_nat_gateway": True,
                "single_nat_gateway": request.environment != "prod",
                "tags": self._common_tags(request),
            },
        ))

    def _add_kubernetes(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        size_cfg = CLUSTER_SIZE_DEFAULTS[request.cluster_size]
        node_pools = [{
            "name": "default",
            "instance_type": _AWS_NODE_INSTANCE_TYPES[request.cluster_size],
            "min_size": size_cfg["min_nodes"],
            "max_size": size_cfg["max_nodes"],
            "desired_size": size_cfg["min_nodes"],
            "labels": {"workload": "general"},
        }]
        if request.enable_gpu:
            node_pools.append({
                "name": "gpu",
                "instance_type": _AWS_GPU_NODE_INSTANCE_TYPES[request.cluster_size],
                "min_size": 0,
                "max_size": max(2, request.gpu_count_per_node or 2),
                "desired_size": 0,
                "labels": {"workload": "gpu", "nvidia.com/gpu": "true"},
                "taints": [{"key": "nvidia.com/gpu", "value": "true", "effect": "NoSchedule"}],
            })
        plan.resources.append(ResourcePlan(
            resource_type="kubernetes_cluster",
            name=self._name(request, "eks"),
            provider=self.PROVIDER,
            settings={
                "k8s_version": "1.29",
                "node_pools": node_pools,
                "enable_logging": True,
                "logging_types": ["api", "audit", "authenticator"],
                "endpoint_private_access": True,
                "endpoint_public_access": request.environment != "prod",
                "tags": self._common_tags(request),
            },
        ))

    def _add_object_storage(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="object_storage",
            name=self._name(request, "models"),
            provider=self.PROVIDER,
            settings={
                "service": "S3",
                "versioning": request.storage_versioning,
                "encryption": "AES256",
                "lifecycle_rules": [
                    {"transition_to_ia_days": 30, "transition_to_glacier_days": 90},
                ],
                "access_logging": request.environment == "prod",
                "tags": self._common_tags(request),
            },
        ))

    def _add_database(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="managed_database",
            name=self._name(request, "postgres"),
            provider=self.PROVIDER,
            settings={
                "service": "RDS",
                "engine": "postgres",
                "engine_version": "15.4",
                "instance_class": _AWS_RDS_INSTANCE_CLASSES[request.cluster_size],
                "allocated_storage_gb": request.database_storage_gb,
                "multi_az": request.enable_ha_database,
                "backup_retention_days": 7 if request.environment == "prod" else 1,
                "storage_encrypted": True,
                "deletion_protection": request.environment == "prod",
                "tags": self._common_tags(request),
            },
        ))

    def _add_cache(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        node_type = _AWS_ELASTICACHE_NODE_TYPES.get(
            request.cache_memory_gb,
            _AWS_ELASTICACHE_NODE_TYPES[2],
        )
        if request.cache_memory_gb not in _AWS_ELASTICACHE_NODE_TYPES:
            plan.warnings.append(
                f"Cache memory {request.cache_memory_gb}GB has no exact AWS match; "
                f"rounded to {node_type}."
            )
        plan.resources.append(ResourcePlan(
            resource_type="managed_cache",
            name=self._name(request, "redis"),
            provider=self.PROVIDER,
            settings={
                "service": "ElastiCache",
                "engine": "redis",
                "engine_version": "7.0",
                "node_type": node_type,
                "num_cache_nodes": 2 if request.enable_ha_database else 1,
                "automatic_failover_enabled": request.enable_ha_database,
                "at_rest_encryption_enabled": True,
                "transit_encryption_enabled": True,
                "tags": self._common_tags(request),
            },
        ))

    def _add_load_balancer(self, plan: InfrastructurePlan) -> None:
        request = plan.request
        plan.resources.append(ResourcePlan(
            resource_type="load_balancer",
            name=self._name(request, "alb"),
            provider=self.PROVIDER,
            settings={
                "service": "ApplicationLoadBalancer",
                "scheme": "internet-facing",
                "ssl_policy": "ELBSecurityPolicy-TLS13-1-2-2021-06",
                "idle_timeout_seconds": 60,
                "tags": self._common_tags(request),
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
                "alerting_targets": ["pagerduty", "slack"],
                "retention_days": 30 if request.environment == "prod" else 7,
                "cloudwatch_log_groups": [
                    f"/aws/eks/{self._name(request, 'eks')}/cluster",
                ],
            },
        ))
