"""Tests for the AWSProvider implementation."""

from datetime import datetime, timedelta

import pytest

from src.cloud_providers.aws import AWSProvider
from src.cloud_providers.base import InstanceFamily, PricingModel


@pytest.fixture
def provider() -> AWSProvider:
    return AWSProvider(region="us-east-1")


class TestAWSProvider:
    def test_initialization_uses_catalog_when_no_session(self, provider: AWSProvider) -> None:
        assert provider.region == "us-east-1"
        assert provider._pricing_client is None
        assert provider._ce_client is None
        assert provider._ec2_client is None

    def test_get_instance_pricing_on_demand(self, provider: AWSProvider) -> None:
        info = provider.get_instance_pricing("m5.large")
        assert info.instance_spec.provider == "aws"
        assert info.instance_spec.vcpus == 2
        assert info.price_per_hour == pytest.approx(0.096)
        assert info.price_per_month == pytest.approx(0.096 * 730)
        assert info.pricing_model == PricingModel.ON_DEMAND

    def test_get_instance_pricing_reservation_discount(self, provider: AWSProvider) -> None:
        on_demand = provider.get_instance_pricing("m5.large", PricingModel.ON_DEMAND)
        reserved = provider.get_instance_pricing("m5.large", PricingModel.RESERVED_3Y)
        assert reserved.price_per_hour < on_demand.price_per_hour
        # 3-year RI is 0.40 of on-demand in our static catalog.
        assert reserved.price_per_hour == pytest.approx(on_demand.price_per_hour * 0.40)

    def test_get_instance_pricing_unknown_type_raises(self, provider: AWSProvider) -> None:
        with pytest.raises(ValueError, match="Unknown AWS instance type"):
            provider.get_instance_pricing("imaginary.huge")

    def test_pricing_is_cached(self, provider: AWSProvider) -> None:
        first = provider.get_instance_pricing("m5.large")
        second = provider.get_instance_pricing("m5.large")
        assert first is second

    def test_list_instance_types_by_family(self, provider: AWSProvider) -> None:
        gpus = provider.list_instance_types(family=InstanceFamily.GPU)
        assert len(gpus) >= 3
        assert all(spec.gpu_count >= 1 for spec in gpus)
        assert all(spec.family == InstanceFamily.GPU for spec in gpus)

    def test_list_instance_types_filters_by_vcpu_and_memory(self, provider: AWSProvider) -> None:
        results = provider.list_instance_types(min_vcpus=8, min_memory_gb=32.0)
        assert results
        assert all(spec.vcpus >= 8 for spec in results)
        assert all(spec.memory_gb >= 32.0 for spec in results)

    def test_storage_pricing_for_standard(self, provider: AWSProvider) -> None:
        pricing = provider.get_storage_pricing("STANDARD")
        assert pricing.provider == "aws"
        assert pricing.price_per_gb_month == pytest.approx(0.023)
        assert pricing.minimum_storage_duration_days == 0

    def test_storage_pricing_unknown_class_raises(self, provider: AWSProvider) -> None:
        with pytest.raises(ValueError, match="Unknown AWS storage class"):
            provider.get_storage_pricing("UNICORN")

    def test_network_pricing_to_internet(self, provider: AWSProvider) -> None:
        result = provider.get_network_pricing("us-east-1", to_internet=True)
        assert result["egress_per_gb"] == pytest.approx(0.09)

    def test_network_pricing_inter_region(self, provider: AWSProvider) -> None:
        result = provider.get_network_pricing("us-east-1", to_region="us-west-2")
        assert result["egress_per_gb"] == pytest.approx(0.02)

    def test_network_pricing_intra_region(self, provider: AWSProvider) -> None:
        result = provider.get_network_pricing("us-east-1", to_region="us-east-1")
        assert result["egress_per_gb"] == pytest.approx(0.01)

    def test_actual_costs_static_dataset(self, provider: AWSProvider) -> None:
        start = datetime(2025, 1, 1)
        end = start + timedelta(days=30)
        costs = provider.get_actual_costs(start, end)
        assert set(costs.keys()) == {"EC2", "S3", "RDS", "DataTransfer", "Other"}
        assert all(value > 0 for value in costs.values())
        # Scales linearly with days.
        costs_double = provider.get_actual_costs(start, start + timedelta(days=60))
        assert costs_double["EC2"] == pytest.approx(costs["EC2"] * 2)

    @pytest.mark.parametrize(
        "instance_type,expected_gpu",
        [
            ("m5.large", 0),
            ("p3.2xlarge", 1),
            ("p3.8xlarge", 4),
            ("g4dn.xlarge", 1),
        ],
    )
    def test_gpu_count_correct(self, provider: AWSProvider, instance_type: str, expected_gpu: int) -> None:
        info = provider.get_instance_pricing(instance_type)
        assert info.instance_spec.gpu_count == expected_gpu

    def test_find_equivalent_instance_for_gpu(self, provider: AWSProvider) -> None:
        target = provider.get_instance_pricing("p3.2xlarge").instance_spec
        match = provider.find_equivalent_instance(target)
        # The target itself is exactly equivalent.
        assert match is not None
        assert match.gpu_type == "V100"
