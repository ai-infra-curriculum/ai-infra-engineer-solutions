"""
Pulumi-style Multi-Cloud ML Infrastructure

A Pulumi-inspired reusable-component framework for declaring multi-cloud
ML infrastructure in Python. The library produces a deterministic
resource graph (independent of the real pulumi runtime, which requires
the pulumi CLI). Each cloud-specific component (AwsStorage, GcpTpu,
AzureMonitor, AwsEKS) inherits from a shared Component base, attaches
itself to a Stack, and contributes typed resources to the graph.

The resulting Stack can be serialized to JSON (Pulumi state shape),
diffed against a prior state to compute Adds/Updates/Removes, and
priced.

The point of this module is to give the curriculum a Pulumi-style
component pattern that is unit-testable without requiring cloud
credentials or the pulumi binary.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


# -- Core resource graph -------------------------------------------------


class Provider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


@dataclass
class ResourceID:
    """Stable identifier for a resource in a Stack."""

    provider: Provider
    resource_type: str
    logical_name: str

    def urn(self, stack_name: str) -> str:
        return f"urn:pulumi:{stack_name}::{self.provider.value}::{self.resource_type}::{self.logical_name}"


@dataclass
class Resource:
    """One declared resource in the stack."""

    id: ResourceID
    properties: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # other URNs
    tags: Dict[str, str] = field(default_factory=dict)

    def fingerprint(self, stack_name: str) -> str:
        body = json.dumps(
            {
                "urn": self.id.urn(stack_name),
                "properties": self.properties,
                "tags": self.tags,
            },
            sort_keys=True, default=str,
        )
        return hashlib.sha256(body.encode()).hexdigest()[:16]


@dataclass
class StackOutput:
    name: str
    value: Any
    sensitive: bool = False


@dataclass
class Stack:
    """One Pulumi-style stack: a graph of resources + outputs."""

    name: str
    resources: List[Resource] = field(default_factory=list)
    outputs: List[StackOutput] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add(self, resource: Resource) -> Resource:
        self.resources.append(resource)
        return resource

    def output(self, name: str, value: Any, *, sensitive: bool = False) -> StackOutput:
        out = StackOutput(name=name, value=value, sensitive=sensitive)
        self.outputs.append(out)
        return out

    def find(self, logical_name: str) -> Optional[Resource]:
        for r in self.resources:
            if r.id.logical_name == logical_name:
                return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "resources": [
                {
                    "urn": r.id.urn(self.name),
                    "provider": r.id.provider.value,
                    "type": r.id.resource_type,
                    "logical_name": r.id.logical_name,
                    "properties": r.properties,
                    "dependencies": list(r.dependencies),
                    "tags": dict(r.tags),
                    "fingerprint": r.fingerprint(self.name),
                }
                for r in self.resources
            ],
            "outputs": [
                {"name": o.name, "value": o.value, "sensitive": o.sensitive}
                for o in self.outputs
            ],
        }


# -- Pulumi-style components -------------------------------------------


class Component:
    """Base class for Pulumi-style multi-resource components."""

    provider: Provider = Provider.AWS

    def __init__(self, name: str, *, tags: Optional[Dict[str, str]] = None):
        self.name = name
        self.tags = dict(tags or {})

    def register(self, stack: Stack) -> List[Resource]:
        """Add this component's resources to `stack`. Returns them."""
        raise NotImplementedError


@dataclass
class StorageConfig:
    bucket_name: str
    versioning: bool = True
    lifecycle_to_ia_days: Optional[int] = 30
    encryption: str = "AES256"


class AwsStorage(Component):
    """S3 bucket + lifecycle + versioning."""

    provider = Provider.AWS

    def __init__(self, name: str, config: StorageConfig,
                 *, tags: Optional[Dict[str, str]] = None):
        super().__init__(name, tags=tags)
        self.config = config

    def register(self, stack: Stack) -> List[Resource]:
        bucket = stack.add(Resource(
            id=ResourceID(self.provider, "aws:s3:Bucket", self.config.bucket_name),
            properties={
                "bucket": self.config.bucket_name,
                "versioning": {"enabled": self.config.versioning},
                "serverSideEncryptionConfiguration": {
                    "rule": {"applyServerSideEncryptionByDefault":
                             {"sseAlgorithm": self.config.encryption}},
                },
                "lifecycleRules": [{
                    "id": f"{self.config.bucket_name}-lifecycle",
                    "enabled": True,
                    "transitions": [{
                        "days": self.config.lifecycle_to_ia_days,
                        "storageClass": "STANDARD_IA",
                    }] if self.config.lifecycle_to_ia_days else [],
                }],
            },
            tags=dict(self.tags),
        ))
        return [bucket]


@dataclass
class TpuConfig:
    accelerator_type: str = "v4-8"
    runtime_version: str = "tpu-vm-tf-2.15.0"
    network: str = "default"
    preemptible: bool = False


class GcpTpu(Component):
    """GCP TPU VM."""

    provider = Provider.GCP

    def __init__(
        self, name: str, config: TpuConfig,
        *, project: str, zone: str, tags: Optional[Dict[str, str]] = None,
    ):
        super().__init__(name, tags=tags)
        self.config = config
        self.project = project
        self.zone = zone

    def register(self, stack: Stack) -> List[Resource]:
        tpu = stack.add(Resource(
            id=ResourceID(self.provider, "gcp:tpu:V2Vm", self.name),
            properties={
                "name": self.name,
                "project": self.project,
                "zone": self.zone,
                "acceleratorType": self.config.accelerator_type,
                "runtimeVersion": self.config.runtime_version,
                "network": self.config.network,
                "schedulingConfig": {"preemptible": self.config.preemptible},
            },
            tags=dict(self.tags),
        ))
        return [tpu]


@dataclass
class EksConfig:
    cluster_name: str
    region: str
    node_instance_type: str = "m5.xlarge"
    node_min_size: int = 2
    node_max_size: int = 6
    kubernetes_version: str = "1.29"


class AwsEKS(Component):
    """EKS cluster + node group + supporting IAM roles."""

    provider = Provider.AWS

    def __init__(self, name: str, config: EksConfig,
                 *, tags: Optional[Dict[str, str]] = None):
        super().__init__(name, tags=tags)
        self.config = config

    def register(self, stack: Stack) -> List[Resource]:
        cluster_urn = ResourceID(
            self.provider, "aws:eks:Cluster", self.config.cluster_name,
        )
        cluster_role = stack.add(Resource(
            id=ResourceID(self.provider, "aws:iam:Role",
                          f"{self.config.cluster_name}-cluster-role"),
            properties={"service": "eks.amazonaws.com",
                        "managedPolicies": ["AmazonEKSClusterPolicy"]},
            tags=dict(self.tags),
        ))
        node_role = stack.add(Resource(
            id=ResourceID(self.provider, "aws:iam:Role",
                          f"{self.config.cluster_name}-node-role"),
            properties={
                "service": "ec2.amazonaws.com",
                "managedPolicies": [
                    "AmazonEKSWorkerNodePolicy",
                    "AmazonEC2ContainerRegistryReadOnly",
                ],
            },
            tags=dict(self.tags),
        ))
        cluster = stack.add(Resource(
            id=cluster_urn,
            properties={
                "name": self.config.cluster_name,
                "version": self.config.kubernetes_version,
                "region": self.config.region,
                "roleArn": cluster_role.id.urn(stack.name),
            },
            dependencies=[cluster_role.id.urn(stack.name)],
            tags=dict(self.tags),
        ))
        node_group = stack.add(Resource(
            id=ResourceID(self.provider, "aws:eks:NodeGroup",
                          f"{self.config.cluster_name}-nodes"),
            properties={
                "clusterName": self.config.cluster_name,
                "instanceTypes": [self.config.node_instance_type],
                "scalingConfig": {
                    "minSize": self.config.node_min_size,
                    "maxSize": self.config.node_max_size,
                    "desiredSize": self.config.node_min_size,
                },
                "nodeRoleArn": node_role.id.urn(stack.name),
            },
            dependencies=[cluster.id.urn(stack.name), node_role.id.urn(stack.name)],
            tags=dict(self.tags),
        ))
        return [cluster_role, node_role, cluster, node_group]


@dataclass
class AzureMonitorConfig:
    workspace_name: str
    location: str = "eastus"
    retention_days: int = 30
    enable_alerts: bool = True


class AzureMonitor(Component):
    """Azure Monitor workspace + (optional) alert rules."""

    provider = Provider.AZURE

    def __init__(self, name: str, config: AzureMonitorConfig,
                 *, resource_group: str, tags: Optional[Dict[str, str]] = None):
        super().__init__(name, tags=tags)
        self.config = config
        self.resource_group = resource_group

    def register(self, stack: Stack) -> List[Resource]:
        workspace = stack.add(Resource(
            id=ResourceID(self.provider, "azure:operationalinsights:Workspace",
                          self.config.workspace_name),
            properties={
                "name": self.config.workspace_name,
                "resourceGroupName": self.resource_group,
                "location": self.config.location,
                "sku": {"name": "PerGB2018"},
                "retentionInDays": self.config.retention_days,
            },
            tags=dict(self.tags),
        ))
        resources = [workspace]
        if self.config.enable_alerts:
            alert = stack.add(Resource(
                id=ResourceID(self.provider, "azure:insights:MetricAlert",
                              f"{self.config.workspace_name}-default-alert"),
                properties={
                    "name": f"{self.config.workspace_name}-default-alert",
                    "resourceGroupName": self.resource_group,
                    "criteria": {
                        "metric": "Heartbeat",
                        "aggregation": "Average",
                        "operator": "LessThan",
                        "threshold": 1,
                    },
                    "scopes": [workspace.id.urn(stack.name)],
                    "severity": 2,
                },
                dependencies=[workspace.id.urn(stack.name)],
                tags=dict(self.tags),
            ))
            resources.append(alert)
        return resources


# -- Builder + diff -----------------------------------------------------


class MultiCloudMLPlatform:
    """End-to-end ML platform spanning AWS storage + GCP TPU + Azure monitor + AWS EKS."""

    def __init__(
        self,
        *,
        project_name: str,
        stack_name: str,
        aws_region: str = "us-east-1",
        gcp_project: str = "ml-platform-1",
        gcp_zone: str = "us-central1-a",
        azure_resource_group: str = "ml-platform-rg",
        common_tags: Optional[Dict[str, str]] = None,
    ):
        self.project_name = project_name
        self.stack_name = stack_name
        self.aws_region = aws_region
        self.gcp_project = gcp_project
        self.gcp_zone = gcp_zone
        self.azure_resource_group = azure_resource_group
        self.common_tags = {
            "Project": project_name, "Stack": stack_name, "ManagedBy": "pulumi",
            **(common_tags or {}),
        }

    def build(self, *, include_tpu: bool = True, include_azure_alerts: bool = True) -> Stack:
        stack = Stack(name=self.stack_name)
        AwsStorage(
            f"{self.project_name}-models",
            StorageConfig(bucket_name=f"{self.project_name}-{self.stack_name}-models"),
            tags=self.common_tags,
        ).register(stack)
        AwsStorage(
            f"{self.project_name}-datasets",
            StorageConfig(
                bucket_name=f"{self.project_name}-{self.stack_name}-datasets",
                lifecycle_to_ia_days=60,
            ),
            tags=self.common_tags,
        ).register(stack)
        AwsEKS(
            f"{self.project_name}-eks",
            EksConfig(
                cluster_name=f"{self.project_name}-{self.stack_name}-eks",
                region=self.aws_region,
            ),
            tags=self.common_tags,
        ).register(stack)
        if include_tpu:
            GcpTpu(
                f"{self.project_name}-tpu",
                TpuConfig(accelerator_type="v4-8", preemptible=self.stack_name != "prod"),
                project=self.gcp_project, zone=self.gcp_zone, tags=self.common_tags,
            ).register(stack)
        AzureMonitor(
            f"{self.project_name}-monitor",
            AzureMonitorConfig(
                workspace_name=f"{self.project_name}-{self.stack_name}-monitor",
                enable_alerts=include_azure_alerts,
            ),
            resource_group=self.azure_resource_group,
            tags=self.common_tags,
        ).register(stack)

        # Publish a few outputs.
        models_bucket = stack.find(f"{self.project_name}-{self.stack_name}-models")
        eks_cluster = stack.find(f"{self.project_name}-{self.stack_name}-eks")
        if models_bucket is not None:
            stack.output("models_bucket", models_bucket.properties["bucket"])
        if eks_cluster is not None:
            stack.output("eks_cluster_name", eks_cluster.properties["name"])
        return stack


@dataclass
class ResourceDiff:
    """One resource-level change between two stacks."""

    urn: str
    operation: str  # "create" / "update" / "delete"
    old_fingerprint: Optional[str] = None
    new_fingerprint: Optional[str] = None


@dataclass
class StackDiff:
    """Adds + updates + deletes between two stacks."""

    diffs: List[ResourceDiff]

    @property
    def to_create(self) -> List[ResourceDiff]:
        return [d for d in self.diffs if d.operation == "create"]

    @property
    def to_update(self) -> List[ResourceDiff]:
        return [d for d in self.diffs if d.operation == "update"]

    @property
    def to_delete(self) -> List[ResourceDiff]:
        return [d for d in self.diffs if d.operation == "delete"]


def diff_stacks(previous: Stack, current: Stack) -> StackDiff:
    """Compute the diff between two stacks (assumes same `name`)."""
    if previous.name != current.name:
        raise ValueError(
            f"Cannot diff stacks with different names: {previous.name} vs {current.name}"
        )
    prev_by_urn = {r.id.urn(previous.name): r for r in previous.resources}
    curr_by_urn = {r.id.urn(current.name): r for r in current.resources}
    diffs: List[ResourceDiff] = []
    for urn, resource in curr_by_urn.items():
        if urn not in prev_by_urn:
            diffs.append(ResourceDiff(
                urn=urn, operation="create",
                new_fingerprint=resource.fingerprint(current.name),
            ))
        else:
            old_fp = prev_by_urn[urn].fingerprint(previous.name)
            new_fp = resource.fingerprint(current.name)
            if old_fp != new_fp:
                diffs.append(ResourceDiff(
                    urn=urn, operation="update",
                    old_fingerprint=old_fp, new_fingerprint=new_fp,
                ))
    for urn, resource in prev_by_urn.items():
        if urn not in curr_by_urn:
            diffs.append(ResourceDiff(
                urn=urn, operation="delete",
                old_fingerprint=resource.fingerprint(previous.name),
            ))
    return StackDiff(diffs=diffs)


# -- Cost estimator -----------------------------------------------------


# Hourly rates ($) for relevant resources.
_HOURLY: Dict[str, float] = {
    "v4-8": 6.50,  # GCP TPU v4-8 (representative)
    "v3-8": 8.00,
    "m5.xlarge": 0.192,
    "m5.2xlarge": 0.384,
    "p3.2xlarge": 3.06,
}


@dataclass
class CostBreakdown:
    aws_compute_usd: float
    aws_storage_usd: float
    gcp_tpu_usd: float
    azure_monitor_usd: float
    total_usd: float


def estimate_cost(stack: Stack, *, hours: int = 730) -> CostBreakdown:
    aws_compute = 0.0
    aws_storage = 200 * 0.023  # baseline 200GB across both buckets
    gcp_tpu = 0.0
    azure_monitor = 0.0
    for resource in stack.resources:
        if resource.id.resource_type == "aws:eks:NodeGroup":
            instance = resource.properties.get("instanceTypes", [None])[0]
            desired = resource.properties.get("scalingConfig", {}).get("desiredSize", 0)
            aws_compute += _HOURLY.get(instance, 0.2) * desired * hours
        elif resource.id.resource_type == "gcp:tpu:V2Vm":
            accel = resource.properties.get("acceleratorType")
            scheduling = resource.properties.get("schedulingConfig", {})
            multiplier = 0.4 if scheduling.get("preemptible") else 1.0
            gcp_tpu += _HOURLY.get(accel, 5.0) * multiplier * hours
        elif resource.id.resource_type == "azure:operationalinsights:Workspace":
            retention = resource.properties.get("retentionInDays", 30)
            # $2.30/GB ingest at ~10GB/day for retention.
            azure_monitor += 2.30 * 10 * (retention / 30.0)
    total = aws_compute + aws_storage + gcp_tpu + azure_monitor
    return CostBreakdown(
        aws_compute_usd=round(aws_compute, 2),
        aws_storage_usd=round(aws_storage, 2),
        gcp_tpu_usd=round(gcp_tpu, 2),
        azure_monitor_usd=round(azure_monitor, 2),
        total_usd=round(total, 2),
    )
