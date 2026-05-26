"""
Cloud ML Infrastructure Provisioner

This package exposes a portable abstraction for declaring an ML
infrastructure stack and emitting a per-cloud deployment plan
(Kubernetes cluster, object storage, managed Postgres, managed Redis,
load balancer, networking, monitoring). The plans can be serialized
to Terraform HCL or JSON for downstream tooling. The package does not
itself call cloud APIs — it produces deterministic plans that an
operator (or CI pipeline) submits to Terraform, Pulumi, or a console.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class CloudProvider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class ClusterSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# Mapping cluster sizes -> portable resource shape. Each provider
# implementation translates these into provider-specific instance types.
CLUSTER_SIZE_DEFAULTS: Dict[ClusterSize, Dict[str, int]] = {
    ClusterSize.SMALL: {"min_nodes": 2, "max_nodes": 5, "vcpu_per_node": 4, "memory_gb_per_node": 16},
    ClusterSize.MEDIUM: {"min_nodes": 3, "max_nodes": 10, "vcpu_per_node": 8, "memory_gb_per_node": 32},
    ClusterSize.LARGE: {"min_nodes": 5, "max_nodes": 20, "vcpu_per_node": 16, "memory_gb_per_node": 64},
}


@dataclass
class InfrastructureRequest:
    """Portable request: identical across providers."""

    project_name: str
    environment: str  # dev / staging / prod
    region: str
    cluster_size: ClusterSize = ClusterSize.SMALL
    enable_gpu: bool = False
    gpu_count_per_node: int = 0
    enable_ha_database: bool = True
    database_storage_gb: int = 100
    cache_memory_gb: int = 2
    storage_versioning: bool = True
    tags: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_envs = {"dev", "staging", "prod"}
        if self.environment not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")


@dataclass
class ResourcePlan:
    """One resource in the infrastructure plan."""

    resource_type: str  # "kubernetes_cluster", "object_storage", etc.
    name: str
    provider: CloudProvider
    settings: Dict[str, object] = field(default_factory=dict)


@dataclass
class InfrastructurePlan:
    """Complete plan for one cloud."""

    provider: CloudProvider
    request: InfrastructureRequest
    resources: List[ResourcePlan] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "provider": self.provider.value,
            "request": asdict(self.request)
            | {"cluster_size": self.request.cluster_size.value},
            "resources": [
                {
                    "resource_type": r.resource_type,
                    "name": r.name,
                    "provider": r.provider.value,
                    "settings": r.settings,
                }
                for r in self.resources
            ],
            "warnings": list(self.warnings),
        }

    def find_resource(self, resource_type: str) -> Optional[ResourcePlan]:
        for r in self.resources:
            if r.resource_type == resource_type:
                return r
        return None


# The actual provisioners are in sibling modules and registered here so
# callers can do `from src.provisioner import get_provisioner`.
def get_provisioner(provider: CloudProvider):
    """Return the concrete provisioner class for the requested cloud."""
    # Imported lazily to avoid import cycles.
    if provider is CloudProvider.AWS:
        from .aws_provisioner import AWSProvisioner
        return AWSProvisioner
    if provider is CloudProvider.GCP:
        from .gcp_provisioner import GCPProvisioner
        return GCPProvisioner
    if provider is CloudProvider.AZURE:
        from .azure_provisioner import AzureProvisioner
        return AzureProvisioner
    raise ValueError(f"Unknown provider: {provider}")
