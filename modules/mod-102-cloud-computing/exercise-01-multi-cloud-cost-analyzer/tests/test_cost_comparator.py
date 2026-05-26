"""Tests for the cross-cloud CostComparator and Optimizer."""

import pytest

from src.cloud_providers.aws import AWSProvider
from src.cloud_providers.azure import AzureProvider
from src.cloud_providers.base import InstanceFamily, PricingModel
from src.cloud_providers.gcp import GCPProvider
from src.cost_comparator import CostComparator, WorkloadSpec
from src.optimizer import Confidence, CostOptimizer, UsageProfile


@pytest.fixture
def providers():
    return {
        "aws": AWSProvider(region="us-east-1"),
        "gcp": GCPProvider(region="us-central1"),
        "azure": AzureProvider(region="eastus"),
    }


@pytest.fixture
def comparator(providers):
    return CostComparator(providers)


class TestCostComparator:
    def test_compare_produces_one_quote_per_provider(self, providers, comparator):
        ref = providers["aws"].get_instance_pricing("m5.xlarge").instance_spec
        workload = WorkloadSpec(reference_instance=ref, storage_gb=500.0, monthly_egress_gb=100.0)
        result = comparator.compare(workload)
        assert len(result.quotes) == 3
        provider_names = {q.provider for q in result.quotes}
        assert provider_names == {"aws", "gcp", "azure"}

    def test_compare_orders_cheapest_first(self, providers, comparator):
        ref = providers["aws"].get_instance_pricing("m5.large").instance_spec
        workload = WorkloadSpec(reference_instance=ref)
        result = comparator.compare(workload)
        costs = [q.total_monthly_cost for q in result.quotes]
        assert costs == sorted(costs)
        assert result.cheapest_provider == result.quotes[0].provider
        assert result.most_expensive_provider == result.quotes[-1].provider

    def test_compare_includes_storage_and_egress(self, providers, comparator):
        ref = providers["aws"].get_instance_pricing("m5.large").instance_spec
        zero = WorkloadSpec(reference_instance=ref)
        with_extras = WorkloadSpec(
            reference_instance=ref,
            storage_gb=1000.0,
            monthly_egress_gb=500.0,
        )
        a = comparator.compare(zero).quotes[0]
        b = comparator.compare(with_extras).quotes[0]
        assert b.total_monthly_cost > a.total_monthly_cost
        assert b.storage_monthly_cost > 0
        assert b.egress_monthly_cost > 0

    def test_compare_spread_percent_is_nonzero(self, providers, comparator):
        ref = providers["aws"].get_instance_pricing("p3.2xlarge").instance_spec
        workload = WorkloadSpec(reference_instance=ref)
        result = comparator.compare(workload)
        assert result.spread_percent > 0

    def test_compare_finds_equivalent_for_cross_cloud_reference(self, providers, comparator):
        # Start from a GCP instance; AWS should find an equivalent.
        gcp_ref = providers["gcp"].get_instance_pricing("n2-standard-4").instance_spec
        workload = WorkloadSpec(reference_instance=gcp_ref)
        result = comparator.compare(workload)
        aws_quote = next(q for q in result.quotes if q.provider == "aws")
        # Same family, comparable size.
        assert aws_quote.instance_pricing.instance_spec.family == gcp_ref.family
        assert aws_quote.instance_pricing.instance_spec.vcpus >= gcp_ref.vcpus * 0.75

    def test_compare_storage_three_providers(self, comparator):
        rows = comparator.compare_storage(size_gb=1000.0)
        assert set(rows.keys()) == {"aws", "gcp", "azure"}
        for value in rows.values():
            assert value["monthly_cost"] > 0
            assert value["price_per_gb_month"] > 0

    def test_empty_provider_dict_rejected(self):
        with pytest.raises(ValueError):
            CostComparator({})


class TestCostOptimizer:
    def test_recommends_rightsizing_when_utilization_low(self, providers):
        optimizer = CostOptimizer(providers["aws"])
        instance = providers["aws"].get_instance_pricing("m5.4xlarge").instance_spec
        usage = UsageProfile(avg_cpu_percent=15.0, avg_memory_percent=20.0, monthly_hours=730.0)
        recs = optimizer.recommend(instance, usage)
        rightsize = [r for r in recs if r.id == "rightsize"]
        assert rightsize
        assert rightsize[0].estimated_monthly_savings_usd > 0

    def test_no_rightsizing_when_utilization_high(self, providers):
        optimizer = CostOptimizer(providers["aws"])
        instance = providers["aws"].get_instance_pricing("m5.large").instance_spec
        usage = UsageProfile(avg_cpu_percent=85.0, avg_memory_percent=80.0)
        recs = optimizer.recommend(instance, usage)
        assert not [r for r in recs if r.id == "rightsize"]

    def test_recommends_reservation_for_steady_workload(self, providers):
        optimizer = CostOptimizer(providers["aws"])
        instance = providers["aws"].get_instance_pricing("m5.xlarge").instance_spec
        usage = UsageProfile(monthly_hours=730.0, age_days=365)
        recs = optimizer.recommend(instance, usage)
        reservations = [r for r in recs if r.id.startswith("reservation_")]
        assert reservations
        # 3-year reservation should beat 1-year savings.
        assert "3y" in reservations[0].id

    def test_no_reservation_for_brand_new_instances(self, providers):
        optimizer = CostOptimizer(providers["aws"])
        instance = providers["aws"].get_instance_pricing("m5.xlarge").instance_spec
        usage = UsageProfile(monthly_hours=730.0, age_days=5)
        recs = optimizer.recommend(instance, usage)
        assert not [r for r in recs if r.id.startswith("reservation_")]

    def test_recommends_spot_for_interruption_tolerant(self, providers):
        optimizer = CostOptimizer(providers["aws"])
        instance = providers["aws"].get_instance_pricing("c5.4xlarge").instance_spec
        usage = UsageProfile(monthly_hours=730.0, interruption_tolerant=True, age_days=10)
        recs = optimizer.recommend(instance, usage)
        spot = [r for r in recs if r.id.startswith("spot_")]
        assert spot

    def test_gpu_idle_recommends_cpu_swap(self, providers):
        optimizer = CostOptimizer(providers["aws"])
        instance = providers["aws"].get_instance_pricing("p3.2xlarge").instance_spec
        usage = UsageProfile(
            avg_cpu_percent=60.0,
            avg_memory_percent=50.0,
            avg_gpu_percent=5.0,
            monthly_hours=730.0,
        )
        recs = optimizer.recommend(instance, usage)
        gpu_recs = [r for r in recs if r.id == "gpu_idle"]
        assert gpu_recs
        assert gpu_recs[0].confidence == Confidence.LOW
        assert gpu_recs[0].estimated_monthly_savings_usd > 0

    def test_recommendations_sorted_by_savings(self, providers):
        optimizer = CostOptimizer(providers["aws"])
        instance = providers["aws"].get_instance_pricing("m5.4xlarge").instance_spec
        usage = UsageProfile(
            avg_cpu_percent=20.0,
            avg_memory_percent=25.0,
            monthly_hours=730.0,
            age_days=400,
            interruption_tolerant=True,
        )
        recs = optimizer.recommend(instance, usage)
        savings = [r.estimated_monthly_savings_usd for r in recs]
        assert savings == sorted(savings, reverse=True)
