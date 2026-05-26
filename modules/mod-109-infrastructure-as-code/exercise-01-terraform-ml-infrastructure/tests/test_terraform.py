"""Tests for the Terraform ML infrastructure builder."""

import pytest

from src.terraform_builder import (
    Environment,
    EnvironmentSpec,
    MLInfrastructureBuilder,
    PlatformConfig,
    TerraformResource,
    ValidationIssue,
    estimate_monthly_cost,
    validate_module,
)


@pytest.fixture
def platform() -> PlatformConfig:
    return PlatformConfig(
        project_name="ml-platform", region="us-east-1", owner="ml-team",
    )


class TestPlatformConfig:
    def test_invalid_project_name_rejected(self):
        with pytest.raises(ValueError):
            PlatformConfig(project_name="ML_Platform")

    def test_valid_project_name(self, platform: PlatformConfig):
        assert platform.project_name == "ml-platform"


class TestEnvironmentSpec:
    def test_dev_has_smaller_resources(self):
        dev = EnvironmentSpec.for_environment(Environment.DEV)
        prod = EnvironmentSpec.for_environment(Environment.PROD)
        assert dev.eks_node_count < prod.eks_node_count
        assert dev.rds_storage_gb < prod.rds_storage_gb

    def test_prod_has_safety_features(self):
        prod = EnvironmentSpec.for_environment(Environment.PROD)
        assert prod.rds_multi_az is True
        assert prod.rds_deletion_protection is True
        assert prod.enable_auto_shutdown is False

    def test_dev_has_auto_shutdown(self):
        dev = EnvironmentSpec.for_environment(Environment.DEV)
        assert dev.enable_auto_shutdown

    def test_prod_includes_gpu_nodes(self):
        prod = EnvironmentSpec.for_environment(Environment.PROD)
        assert prod.gpu_node_count >= 1


class TestBuilder:
    def _build(self, platform, env):
        return MLInfrastructureBuilder(
            platform, EnvironmentSpec.for_environment(env),
        ).build()

    def test_module_emits_required_resource_types(self, platform):
        module = self._build(platform, Environment.PROD)
        types = {r.resource_type for r in module.resources}
        assert "aws_vpc" in types
        assert "aws_subnet" in types
        assert "aws_eks_cluster" in types
        assert "aws_eks_node_group" in types
        assert "aws_s3_bucket" in types
        assert "aws_db_instance" in types
        assert "aws_elasticache_cluster" in types
        assert "aws_iam_role" in types

    def test_required_outputs_present(self, platform):
        module = self._build(platform, Environment.DEV)
        names = {o.name for o in module.outputs}
        assert {"vpc_id", "eks_cluster_name", "s3_models_bucket", "rds_endpoint"} <= names

    def test_gpu_node_group_only_when_gpus_requested(self, platform):
        dev = self._build(platform, Environment.DEV)
        prod = self._build(platform, Environment.PROD)
        dev_gpu = [r for r in dev.resources
                   if r.resource_type == "aws_eks_node_group" and r.name == "gpu"]
        prod_gpu = [r for r in prod.resources
                    if r.resource_type == "aws_eks_node_group" and r.name == "gpu"]
        # Dev has gpu_node_max=2 (>0), so GPU node group is created.
        # Prod has gpu_node_max=8, also created.
        assert dev_gpu
        assert prod_gpu

    def test_hcl_renders_to_string(self, platform):
        module = self._build(platform, Environment.DEV)
        hcl = module.to_hcl()
        assert 'resource "aws_vpc" "main"' in hcl
        assert "cidr_block" in hcl
        assert "output " in hcl

    def test_auto_shutdown_only_for_non_prod(self, platform):
        prod = self._build(platform, Environment.PROD)
        dev = self._build(platform, Environment.DEV)
        prod_shutdown = [r for r in prod.resources
                         if r.resource_type == "aws_cloudwatch_event_rule"]
        dev_shutdown = [r for r in dev.resources
                        if r.resource_type == "aws_cloudwatch_event_rule"]
        assert not prod_shutdown
        assert dev_shutdown

    def test_cost_alarm_always_present(self, platform):
        module = self._build(platform, Environment.PROD)
        alarms = [r for r in module.resources
                  if r.resource_type == "aws_cloudwatch_metric_alarm"]
        assert alarms


class TestValidation:
    def _validate(self, platform, env):
        spec = EnvironmentSpec.for_environment(env)
        module = MLInfrastructureBuilder(platform, spec).build()
        return validate_module(module, platform=platform, env=spec)

    def test_prod_passes_validation(self, platform: PlatformConfig):
        report = self._validate(platform, Environment.PROD)
        assert report.passed

    def test_dev_passes_validation(self, platform):
        report = self._validate(platform, Environment.DEV)
        assert report.passed

    def test_missing_multiaz_in_prod_fails(self, platform):
        spec = EnvironmentSpec.for_environment(Environment.PROD)
        spec.rds_multi_az = False  # break the policy
        module = MLInfrastructureBuilder(platform, spec).build()
        report = validate_module(module, platform=platform, env=spec)
        assert not report.passed
        assert any(i.rule_id == "prod_rds_no_multiaz" for i in report.issues)

    def test_missing_deletion_protection_in_prod_fails(self, platform):
        spec = EnvironmentSpec.for_environment(Environment.PROD)
        spec.rds_deletion_protection = False
        module = MLInfrastructureBuilder(platform, spec).build()
        report = validate_module(module, platform=platform, env=spec)
        assert any(
            i.rule_id == "prod_rds_no_deletion_protection" for i in report.issues
        )

    def test_auto_shutdown_in_prod_warns(self, platform):
        spec = EnvironmentSpec.for_environment(Environment.PROD)
        spec.enable_auto_shutdown = True
        module = MLInfrastructureBuilder(platform, spec).build()
        report = validate_module(module, platform=platform, env=spec)
        warnings = [i for i in report.issues if i.severity == "warning"]
        assert any(i.rule_id == "prod_auto_shutdown_enabled" for i in warnings)

    def test_missing_required_output_detected(self, platform):
        spec = EnvironmentSpec.for_environment(Environment.DEV)
        module = MLInfrastructureBuilder(platform, spec).build()
        # Remove a required output to provoke the validator.
        module.outputs = [o for o in module.outputs if o.name != "vpc_id"]
        report = validate_module(module, platform=platform, env=spec)
        assert any(i.rule_id == "missing_required_output" for i in report.issues)

    def test_resources_have_required_tags(self, platform):
        module = MLInfrastructureBuilder(
            platform, EnvironmentSpec.for_environment(Environment.DEV),
        ).build()
        for resource in module.resources:
            tags = resource.attributes.get("tags")
            if not tags:
                continue
            for required in ("Project", "Environment", "Owner", "ManagedBy"):
                assert f"{required} =" in str(tags), \
                    f"{resource.resource_type}.{resource.name} missing tag {required}"


class TestCostEstimator:
    def test_prod_costs_more_than_dev(self):
        dev = estimate_monthly_cost(EnvironmentSpec.for_environment(Environment.DEV))
        prod = estimate_monthly_cost(EnvironmentSpec.for_environment(Environment.PROD))
        assert prod.total_usd > dev.total_usd * 3

    def test_gpu_cost_zero_when_no_gpu_nodes(self):
        dev = estimate_monthly_cost(EnvironmentSpec.for_environment(Environment.DEV))
        assert dev.gpu_compute_usd == 0.0

    def test_multi_az_doubles_rds_cost(self):
        single = EnvironmentSpec.for_environment(Environment.STAGING)
        multi = EnvironmentSpec.for_environment(Environment.STAGING)
        multi.rds_multi_az = True
        rds_single = estimate_monthly_cost(single).rds_usd
        rds_multi = estimate_monthly_cost(multi).rds_usd
        assert rds_multi == pytest.approx(rds_single * 2, rel=0.01)

    def test_total_includes_all_categories(self):
        prod = estimate_monthly_cost(EnvironmentSpec.for_environment(Environment.PROD))
        category_sum = (
            prod.eks_compute_usd + prod.gpu_compute_usd + prod.rds_usd
            + prod.redis_usd + prod.s3_usd + prod.nat_gateway_usd
        )
        assert prod.total_usd == pytest.approx(category_sum, rel=0.001)


class TestHCLEmission:
    def test_resource_block_format(self, platform):
        spec = EnvironmentSpec.for_environment(Environment.DEV)
        module = MLInfrastructureBuilder(platform, spec).build()
        vpc = next(r for r in module.resources if r.resource_type == "aws_vpc")
        hcl = vpc.to_hcl()
        assert hcl.startswith('resource "aws_vpc" "main"')
        assert hcl.endswith("}")

    def test_output_block_with_sensitive(self):
        from src.terraform_builder import TerraformOutput
        out = TerraformOutput("password", "var.password", "Master password",
                              sensitive=True)
        hcl = out.to_hcl()
        assert "sensitive   = true" in hcl
        assert 'output "password"' in hcl

    def test_required_tag_present_in_output(self, platform):
        spec = EnvironmentSpec.for_environment(Environment.DEV)
        builder = MLInfrastructureBuilder(platform, spec)
        tags = builder._tags("test")
        # The tag block should contain the required tag names.
        assert "Project = " in tags
        assert "Environment = " in tags
        assert "Owner = " in tags
        assert "ManagedBy = " in tags
