"""
Terraform HCL Builder for ML Infrastructure

Produces a complete Terraform module set for an ML platform on AWS:
VPC + subnets, EKS cluster with a GPU node group, S3 model + dataset
buckets, RDS Postgres, ElastiCache Redis, IAM roles, security groups,
and outputs. The builder emits real HCL the consumer can `terraform
plan` against.

Supports environment-specific overrides (dev/staging/prod), cost
estimation, validation (RFC 1123 names, required-tag enforcement,
deletion-protection in prod), and tagging discipline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# -- Configuration types ------------------------------------------------


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


_NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
_REQUIRED_TAGS = ("Project", "Environment", "Owner", "ManagedBy")


@dataclass
class EnvironmentSpec:
    """Per-environment sizing + retention overrides."""

    environment: Environment
    eks_node_count: int = 3
    eks_node_max: int = 5
    eks_node_instance_type: str = "m5.xlarge"
    gpu_node_count: int = 0
    gpu_node_max: int = 4
    gpu_instance_type: str = "p3.2xlarge"
    rds_instance_class: str = "db.t3.medium"
    rds_storage_gb: int = 100
    rds_multi_az: bool = False
    rds_backup_retention_days: int = 7
    rds_deletion_protection: bool = False
    redis_node_type: str = "cache.t3.micro"
    redis_num_cache_nodes: int = 1
    s3_versioning: bool = True
    s3_lifecycle_to_ia_days: int = 30
    s3_lifecycle_to_glacier_days: int = 90
    enable_auto_shutdown: bool = True
    cost_alarm_monthly_usd: float = 1500.0

    @classmethod
    def for_environment(cls, env: Environment) -> "EnvironmentSpec":
        if env is Environment.DEV:
            return cls(
                environment=env,
                eks_node_count=2, eks_node_max=3,
                gpu_node_count=0, gpu_node_max=2,
                rds_instance_class="db.t3.small", rds_storage_gb=20,
                rds_multi_az=False, rds_deletion_protection=False,
                rds_backup_retention_days=1,
                redis_node_type="cache.t3.micro", redis_num_cache_nodes=1,
                enable_auto_shutdown=True,
                cost_alarm_monthly_usd=500.0,
            )
        if env is Environment.STAGING:
            return cls(
                environment=env,
                eks_node_count=3, eks_node_max=6,
                gpu_node_count=0, gpu_node_max=2,
                rds_instance_class="db.t3.medium", rds_storage_gb=50,
                rds_multi_az=False, rds_deletion_protection=False,
                rds_backup_retention_days=3,
                redis_node_type="cache.t3.small", redis_num_cache_nodes=1,
                enable_auto_shutdown=True,
                cost_alarm_monthly_usd=1500.0,
            )
        return cls(
            environment=env,
            eks_node_count=5, eks_node_max=15,
            gpu_node_count=2, gpu_node_max=8,
            eks_node_instance_type="m5.2xlarge",
            rds_instance_class="db.m5.large", rds_storage_gb=500,
            rds_multi_az=True, rds_deletion_protection=True,
            rds_backup_retention_days=30,
            redis_node_type="cache.m5.large", redis_num_cache_nodes=2,
            enable_auto_shutdown=False,
            cost_alarm_monthly_usd=10000.0,
        )


@dataclass
class PlatformConfig:
    """Project-wide settings that span all environments."""

    project_name: str
    region: str = "us-east-1"
    owner: str = "ml-platform"
    extra_tags: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.project_name):
            raise ValueError(
                f"project_name {self.project_name!r} must match RFC 1123 label"
            )


# -- HCL emitter --------------------------------------------------------


@dataclass
class TerraformResource:
    """One Terraform resource block."""

    resource_type: str  # e.g. "aws_vpc"
    name: str  # local name in the module
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_hcl(self) -> str:
        body = _render_block(self.attributes, indent=2)
        return f'resource "{self.resource_type}" "{self.name}" {{\n{body}\n}}'


@dataclass
class TerraformOutput:
    name: str
    value: str
    description: str = ""
    sensitive: bool = False

    def to_hcl(self) -> str:
        body = [f"  value       = {self.value}"]
        if self.description:
            body.insert(0, f'  description = "{self.description}"')
        if self.sensitive:
            body.append("  sensitive   = true")
        return f'output "{self.name}" {{\n' + "\n".join(body) + "\n}"


@dataclass
class TerraformModuleSet:
    """All resources + outputs for one Terraform deployment."""

    resources: List[TerraformResource] = field(default_factory=list)
    outputs: List[TerraformOutput] = field(default_factory=list)

    def to_hcl(self) -> str:
        parts = [r.to_hcl() for r in self.resources]
        parts.extend(o.to_hcl() for o in self.outputs)
        return "\n\n".join(parts) + "\n"


# -- Main builder -------------------------------------------------------


class MLInfrastructureBuilder:
    """Build a complete ML infrastructure Terraform module for one environment."""

    def __init__(self, platform: PlatformConfig, env: EnvironmentSpec):
        self.platform = platform
        self.env = env

    def build(self) -> TerraformModuleSet:
        module = TerraformModuleSet()
        module.resources.extend(self._vpc_resources())
        module.resources.extend(self._eks_resources())
        module.resources.extend(self._s3_resources())
        module.resources.extend(self._rds_resources())
        module.resources.extend(self._redis_resources())
        module.resources.extend(self._iam_resources())
        if self.env.enable_auto_shutdown:
            module.resources.extend(self._auto_shutdown_resources())
        module.resources.extend(self._cost_alarm_resources())
        module.outputs.extend(self._outputs())
        return module

    # -- per-resource emitters ----------------------------------------

    def _vpc_resources(self) -> List[TerraformResource]:
        prefix = self._name("vpc")
        tags = self._tags("vpc")
        return [
            TerraformResource("aws_vpc", "main", {
                "cidr_block": '"10.0.0.0/16"',
                "enable_dns_hostnames": "true",
                "enable_dns_support": "true",
                "tags": tags,
            }),
            TerraformResource("aws_subnet", "private_a", {
                "vpc_id": "aws_vpc.main.id",
                "cidr_block": '"10.0.1.0/24"',
                "availability_zone": f'"{self.platform.region}a"',
                "tags": self._tags("subnet-private-a"),
            }),
            TerraformResource("aws_subnet", "private_b", {
                "vpc_id": "aws_vpc.main.id",
                "cidr_block": '"10.0.2.0/24"',
                "availability_zone": f'"{self.platform.region}b"',
                "tags": self._tags("subnet-private-b"),
            }),
            TerraformResource("aws_subnet", "public_a", {
                "vpc_id": "aws_vpc.main.id",
                "cidr_block": '"10.0.101.0/24"',
                "availability_zone": f'"{self.platform.region}a"',
                "map_public_ip_on_launch": "true",
                "tags": self._tags("subnet-public-a"),
            }),
            TerraformResource("aws_internet_gateway", "main", {
                "vpc_id": "aws_vpc.main.id",
                "tags": tags,
            }),
        ]

    def _eks_resources(self) -> List[TerraformResource]:
        resources = [
            TerraformResource("aws_eks_cluster", "main", {
                "name": f'"{self._name("eks")}"',
                "role_arn": "aws_iam_role.eks_cluster.arn",
                "version": '"1.29"',
                "vpc_config": _block({
                    "subnet_ids": "[aws_subnet.private_a.id, aws_subnet.private_b.id]",
                    "endpoint_private_access": "true",
                    "endpoint_public_access": str(self.env.environment is not Environment.PROD).lower(),
                }),
                "tags": self._tags("eks"),
            }),
            TerraformResource("aws_eks_node_group", "default", {
                "cluster_name": "aws_eks_cluster.main.name",
                "node_group_name": '"default"',
                "node_role_arn": "aws_iam_role.eks_node.arn",
                "subnet_ids": "[aws_subnet.private_a.id, aws_subnet.private_b.id]",
                "scaling_config": _block({
                    "min_size": str(self.env.eks_node_count),
                    "max_size": str(self.env.eks_node_max),
                    "desired_size": str(self.env.eks_node_count),
                }),
                "instance_types": f'["{self.env.eks_node_instance_type}"]',
                "tags": self._tags("eks-nodes"),
            }),
        ]
        if self.env.gpu_node_max > 0:
            resources.append(TerraformResource("aws_eks_node_group", "gpu", {
                "cluster_name": "aws_eks_cluster.main.name",
                "node_group_name": '"gpu"',
                "node_role_arn": "aws_iam_role.eks_node.arn",
                "subnet_ids": "[aws_subnet.private_a.id, aws_subnet.private_b.id]",
                "scaling_config": _block({
                    "min_size": str(self.env.gpu_node_count),
                    "max_size": str(self.env.gpu_node_max),
                    "desired_size": str(self.env.gpu_node_count),
                }),
                "instance_types": f'["{self.env.gpu_instance_type}"]',
                "taint": _block({
                    "key": '"nvidia.com/gpu"',
                    "value": '"true"',
                    "effect": '"NO_SCHEDULE"',
                }),
                "labels": _block({"workload": '"gpu"'}),
                "tags": self._tags("eks-gpu-nodes"),
            }))
        return resources

    def _s3_resources(self) -> List[TerraformResource]:
        resources = []
        for purpose in ("models", "datasets"):
            bucket_name = f'"{self._name(f"s3-{purpose}")}-${{random_id.bucket_suffix.hex}}"'
            resources.append(TerraformResource("aws_s3_bucket", purpose, {
                "bucket": bucket_name,
                "tags": self._tags(f"s3-{purpose}"),
            }))
            resources.append(TerraformResource("aws_s3_bucket_versioning", purpose, {
                "bucket": f"aws_s3_bucket.{purpose}.id",
                "versioning_configuration": _block({
                    "status": '"Enabled"' if self.env.s3_versioning else '"Suspended"',
                }),
            }))
            resources.append(TerraformResource("aws_s3_bucket_lifecycle_configuration", purpose, {
                "bucket": f"aws_s3_bucket.{purpose}.id",
                "rule": _block({
                    "id": f'"{purpose}-lifecycle"',
                    "status": '"Enabled"',
                    "transition": _block({
                        "days": str(self.env.s3_lifecycle_to_ia_days),
                        "storage_class": '"STANDARD_IA"',
                    }),
                }),
            }))
        resources.append(TerraformResource("random_id", "bucket_suffix", {
            "byte_length": "4",
        }))
        return resources

    def _rds_resources(self) -> List[TerraformResource]:
        return [
            TerraformResource("aws_db_subnet_group", "main", {
                "name": f'"{self._name("db-subnets")}"',
                "subnet_ids": "[aws_subnet.private_a.id, aws_subnet.private_b.id]",
                "tags": self._tags("db-subnets"),
            }),
            TerraformResource("aws_db_instance", "main", {
                "identifier": f'"{self._name("postgres")}"',
                "engine": '"postgres"',
                "engine_version": '"15.4"',
                "instance_class": f'"{self.env.rds_instance_class}"',
                "allocated_storage": str(self.env.rds_storage_gb),
                "db_subnet_group_name": "aws_db_subnet_group.main.name",
                "multi_az": str(self.env.rds_multi_az).lower(),
                "backup_retention_period": str(self.env.rds_backup_retention_days),
                "deletion_protection": str(self.env.rds_deletion_protection).lower(),
                "storage_encrypted": "true",
                "skip_final_snapshot": str(self.env.environment is Environment.DEV).lower(),
                "tags": self._tags("postgres"),
            }),
        ]

    def _redis_resources(self) -> List[TerraformResource]:
        return [
            TerraformResource("aws_elasticache_subnet_group", "main", {
                "name": f'"{self._name("redis-subnets")}"',
                "subnet_ids": "[aws_subnet.private_a.id, aws_subnet.private_b.id]",
            }),
            TerraformResource("aws_elasticache_cluster", "main", {
                "cluster_id": f'"{self._name("redis")}"',
                "engine": '"redis"',
                "node_type": f'"{self.env.redis_node_type}"',
                "num_cache_nodes": str(self.env.redis_num_cache_nodes),
                "subnet_group_name": "aws_elasticache_subnet_group.main.name",
                "tags": self._tags("redis"),
            }),
        ]

    def _iam_resources(self) -> List[TerraformResource]:
        return [
            TerraformResource("aws_iam_role", "eks_cluster", {
                "name": f'"{self._name("eks-cluster")}"',
                "assume_role_policy": _trust_policy("eks.amazonaws.com"),
                "tags": self._tags("eks-cluster-role"),
            }),
            TerraformResource("aws_iam_role", "eks_node", {
                "name": f'"{self._name("eks-node")}"',
                "assume_role_policy": _trust_policy("ec2.amazonaws.com"),
                "tags": self._tags("eks-node-role"),
            }),
        ]

    def _auto_shutdown_resources(self) -> List[TerraformResource]:
        """Schedule-based teardown for non-prod environments."""
        return [
            TerraformResource("aws_cloudwatch_event_rule", "auto_shutdown", {
                "name": f'"{self._name("auto-shutdown")}"',
                "description": '"Shut down ML infrastructure outside business hours"',
                "schedule_expression": '"cron(0 22 * * ? *)"',  # 10 PM UTC daily
                "tags": self._tags("auto-shutdown"),
            }),
        ]

    def _cost_alarm_resources(self) -> List[TerraformResource]:
        return [
            TerraformResource("aws_cloudwatch_metric_alarm", "monthly_cost", {
                "alarm_name": f'"{self._name("monthly-cost-alarm")}"',
                "comparison_operator": '"GreaterThanThreshold"',
                "evaluation_periods": "1",
                "metric_name": '"EstimatedCharges"',
                "namespace": '"AWS/Billing"',
                "period": "86400",
                "statistic": '"Maximum"',
                "threshold": str(self.env.cost_alarm_monthly_usd),
                "alarm_description": (
                    f'"Monthly cost alarm at ${self.env.cost_alarm_monthly_usd}"'
                ),
                "tags": self._tags("cost-alarm"),
            }),
        ]

    def _outputs(self) -> List[TerraformOutput]:
        return [
            TerraformOutput("vpc_id", "aws_vpc.main.id", "Main VPC ID"),
            TerraformOutput("eks_cluster_name", "aws_eks_cluster.main.name",
                            "EKS cluster name"),
            TerraformOutput("eks_cluster_endpoint", "aws_eks_cluster.main.endpoint",
                            "EKS API endpoint", sensitive=True),
            TerraformOutput("s3_models_bucket", "aws_s3_bucket.models.id",
                            "S3 bucket for model artifacts"),
            TerraformOutput("rds_endpoint", "aws_db_instance.main.endpoint",
                            "Postgres endpoint", sensitive=True),
            TerraformOutput("redis_endpoint",
                            "aws_elasticache_cluster.main.cache_nodes[0].address",
                            "Redis primary endpoint", sensitive=True),
        ]

    # -- helpers ------------------------------------------------------

    def _name(self, suffix: str) -> str:
        return f"{self.platform.project_name}-{self.env.environment.value}-{suffix}"

    def _tags(self, name: str) -> str:
        tags = {
            "Project": self.platform.project_name,
            "Environment": self.env.environment.value,
            "Owner": self.platform.owner,
            "ManagedBy": "terraform",
            "Name": f"{self.platform.project_name}-{self.env.environment.value}-{name}",
        }
        tags.update(self.platform.extra_tags)
        return _render_map(tags)


# -- HCL rendering helpers ---------------------------------------------


def _render_block(attrs: Dict[str, Any], *, indent: int = 2) -> str:
    """Render a flat attribute map as the body of an HCL block."""
    pad = " " * indent
    lines = []
    for key, value in attrs.items():
        if isinstance(value, str) and value.startswith("__BLOCK__"):
            block_body = value[len("__BLOCK__"):]
            lines.append(f"{pad}{key} {{\n{_indent(block_body, indent + 2)}\n{pad}}}")
        else:
            lines.append(f"{pad}{key} = {value}")
    return "\n".join(lines)


def _block(body: Dict[str, Any]) -> str:
    """Mark a value as a nested block (rendered with `{ … }` not `=`)."""
    inner = _render_block(body, indent=4)
    return "__BLOCK__" + inner


def _render_map(items: Dict[str, str]) -> str:
    body = "\n".join(f'    {key} = "{value}"' for key, value in items.items())
    return "{\n" + body + "\n  }"


def _trust_policy(service: str) -> str:
    return (
        '<<-EOT\n'
        '    {\n'
        '      "Version": "2012-10-17",\n'
        '      "Statement": [\n'
        '        {\n'
        '          "Effect": "Allow",\n'
        f'          "Principal": {{"Service": "{service}"}},\n'
        '          "Action": "sts:AssumeRole"\n'
        '        }\n'
        '      ]\n'
        '    }\n'
        '  EOT'
    )


def _indent(text: str, pad: int) -> str:
    pad_str = " " * pad
    return "\n".join(pad_str + line.lstrip(" ") if line.strip() else line
                     for line in text.splitlines())


# -- Validators ---------------------------------------------------------


@dataclass(frozen=True)
class ValidationIssue:
    rule_id: str
    severity: str  # "info" / "warning" / "error"
    message: str


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def passed(self) -> bool:
        return not self.errors


def validate_module(
    module: TerraformModuleSet,
    *,
    platform: PlatformConfig,
    env: EnvironmentSpec,
) -> ValidationReport:
    report = ValidationReport()

    # 1. RFC 1123 names on resources that carry a name attribute.
    for resource in module.resources:
        name_attr = resource.attributes.get("name") or resource.attributes.get("cluster_id")
        if isinstance(name_attr, str):
            literal = name_attr.strip('"')
            # Ignore values that include a Terraform interpolation.
            if "${" not in literal and not _NAME_RE.match(literal):
                report.issues.append(ValidationIssue(
                    rule_id="invalid_name",
                    severity="error",
                    message=(
                        f"{resource.resource_type}.{resource.name} name "
                        f"{literal!r} does not match RFC 1123 label."
                    ),
                ))

    # 2. Required tags on tag-carrying resources.
    for resource in module.resources:
        if "tags" not in resource.attributes:
            continue
        tag_block = str(resource.attributes["tags"])
        for tag in _REQUIRED_TAGS:
            if f"{tag} =" not in tag_block:
                report.issues.append(ValidationIssue(
                    rule_id="missing_required_tag",
                    severity="error",
                    message=(
                        f"{resource.resource_type}.{resource.name} is missing "
                        f"required tag {tag!r}."
                    ),
                ))

    # 3. Prod-only safety rules.
    if env.environment is Environment.PROD:
        if not env.rds_multi_az:
            report.issues.append(ValidationIssue(
                rule_id="prod_rds_no_multiaz", severity="error",
                message="Production RDS must have multi_az=true.",
            ))
        if not env.rds_deletion_protection:
            report.issues.append(ValidationIssue(
                rule_id="prod_rds_no_deletion_protection", severity="error",
                message="Production RDS must have deletion_protection=true.",
            ))
        if env.enable_auto_shutdown:
            report.issues.append(ValidationIssue(
                rule_id="prod_auto_shutdown_enabled", severity="warning",
                message="Production environment has auto-shutdown enabled; "
                        "scheduled teardown is rarely safe in prod.",
            ))

    # 4. Required outputs.
    required_outputs = {"vpc_id", "eks_cluster_name", "s3_models_bucket"}
    present = {o.name for o in module.outputs}
    missing = required_outputs - present
    for name in missing:
        report.issues.append(ValidationIssue(
            rule_id="missing_required_output", severity="error",
            message=f"Required output {name!r} is missing from module.",
        ))

    return report


# -- Cost estimator ----------------------------------------------------


# Hourly costs in USD (approximate on-demand pricing).
_HOURLY_COSTS: Dict[str, float] = {
    "m5.xlarge": 0.192,
    "m5.2xlarge": 0.384,
    "m5.4xlarge": 0.768,
    "p3.2xlarge": 3.06,
    "p3.8xlarge": 12.24,
    "g4dn.xlarge": 0.526,
    "db.t3.small": 0.034,
    "db.t3.medium": 0.068,
    "db.m5.large": 0.171,
    "db.m5.xlarge": 0.342,
    "cache.t3.micro": 0.017,
    "cache.t3.small": 0.034,
    "cache.m5.large": 0.144,
}

_S3_COST_PER_GB_MONTH = 0.023
_RDS_STORAGE_PER_GB_MONTH = 0.115


@dataclass
class CostEstimate:
    """Monthly cost breakdown."""

    eks_compute_usd: float
    gpu_compute_usd: float
    rds_usd: float
    redis_usd: float
    s3_usd: float  # assumes 100GB baseline
    nat_gateway_usd: float = 32.40  # ~$0.045/hour × 720
    total_usd: float = 0.0

    def __post_init__(self) -> None:
        self.total_usd = round(
            self.eks_compute_usd + self.gpu_compute_usd + self.rds_usd
            + self.redis_usd + self.s3_usd + self.nat_gateway_usd, 2,
        )


def estimate_monthly_cost(env: EnvironmentSpec) -> CostEstimate:
    hours_per_month = 730
    eks = _HOURLY_COSTS.get(env.eks_node_instance_type, 0.2) * env.eks_node_count * hours_per_month
    gpu = (
        _HOURLY_COSTS.get(env.gpu_instance_type, 3.0)
        * env.gpu_node_count * hours_per_month
    )
    rds = (
        _HOURLY_COSTS.get(env.rds_instance_class, 0.1) * hours_per_month
        + env.rds_storage_gb * _RDS_STORAGE_PER_GB_MONTH
    )
    if env.rds_multi_az:
        rds *= 2
    redis = _HOURLY_COSTS.get(env.redis_node_type, 0.02) * env.redis_num_cache_nodes * hours_per_month
    s3 = 100 * _S3_COST_PER_GB_MONTH  # baseline 100GB per bucket × 2 ≈ 200GB
    return CostEstimate(
        eks_compute_usd=round(eks, 2),
        gpu_compute_usd=round(gpu, 2),
        rds_usd=round(rds, 2),
        redis_usd=round(redis, 2),
        s3_usd=round(s3 * 2, 2),
    )
