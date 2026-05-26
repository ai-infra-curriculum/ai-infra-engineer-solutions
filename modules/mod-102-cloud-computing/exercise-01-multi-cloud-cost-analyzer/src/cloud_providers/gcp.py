"""
GCP Cloud Provider Implementation

CloudProvider implementation for Google Cloud. Like the AWS module, this
ships with a static catalog so the analyzer is runnable without GCP
credentials; a `client` argument can be passed at construction time to
enable live Cloud Billing API queries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import (
    CloudProvider,
    InstanceFamily,
    InstanceSpec,
    PricingInfo,
    PricingModel,
    StoragePricing,
)

# Static GCE catalog with representative on-demand pricing in us-central1.
_GCP_INSTANCE_CATALOG: Dict[str, Dict[str, Any]] = {
    "e2-standard-2": {"vcpus": 2, "memory_gb": 8.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.067},
    "e2-standard-4": {"vcpus": 4, "memory_gb": 16.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.134},
    "n2-standard-2": {"vcpus": 2, "memory_gb": 8.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.0971},
    "n2-standard-4": {"vcpus": 4, "memory_gb": 16.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.1942},
    "n2-standard-8": {"vcpus": 8, "memory_gb": 32.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.3885},
    "n2-standard-16": {"vcpus": 16, "memory_gb": 64.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.777},
    "c2-standard-4": {"vcpus": 4, "memory_gb": 16.0, "family": InstanceFamily.COMPUTE_OPTIMIZED, "on_demand": 0.2088},
    "c2-standard-16": {"vcpus": 16, "memory_gb": 64.0, "family": InstanceFamily.COMPUTE_OPTIMIZED, "on_demand": 0.8352},
    "m1-megamem-96": {"vcpus": 96, "memory_gb": 1433.6, "family": InstanceFamily.MEMORY_OPTIMIZED, "on_demand": 10.674},
    "n1-standard-4-t4": {
        "vcpus": 4, "memory_gb": 15.0, "family": InstanceFamily.GPU,
        "gpu_count": 1, "gpu_type": "T4", "on_demand": 0.535,
    },
    "n1-standard-8-v100": {
        "vcpus": 8, "memory_gb": 30.0, "family": InstanceFamily.GPU,
        "gpu_count": 1, "gpu_type": "V100", "on_demand": 2.55,
    },
    "a2-highgpu-1g": {
        "vcpus": 12, "memory_gb": 85.0, "family": InstanceFamily.GPU,
        "gpu_count": 1, "gpu_type": "A100", "on_demand": 3.673,
    },
    "a2-highgpu-8g": {
        "vcpus": 96, "memory_gb": 680.0, "family": InstanceFamily.GPU,
        "gpu_count": 8, "gpu_type": "A100", "on_demand": 29.387,
    },
}

# GCP has sustained-use discounts baked into on-demand automatically;
# committed-use discounts vary by family. These multipliers approximate
# the published averages.
_GCP_PRICING_MULTIPLIERS: Dict[PricingModel, float] = {
    PricingModel.ON_DEMAND: 1.0,
    PricingModel.RESERVED_1Y: 0.63,
    PricingModel.RESERVED_3Y: 0.45,
    PricingModel.PREEMPTIBLE: 0.20,
    PricingModel.SPOT: 0.20,
}

_GCP_STORAGE_CATALOG: Dict[str, Dict[str, float]] = {
    "STANDARD": {"price_per_gb_month": 0.020, "retrieval_fee_per_gb": 0.0, "minimum_days": 0},
    "NEARLINE": {"price_per_gb_month": 0.010, "retrieval_fee_per_gb": 0.01, "minimum_days": 30},
    "COLDLINE": {"price_per_gb_month": 0.004, "retrieval_fee_per_gb": 0.02, "minimum_days": 90},
    "ARCHIVE": {"price_per_gb_month": 0.0012, "retrieval_fee_per_gb": 0.05, "minimum_days": 365},
}

_GCP_NETWORK_PRICING: Dict[str, float] = {
    "internet_egress_per_gb": 0.085,
    "inter_region_per_gb": 0.01,
    "intra_region_per_gb": 0.01,
}


class GCPProvider(CloudProvider):
    """GCP pricing and billing provider."""

    def __init__(self, region: str = "us-central1", *, client: Optional[Any] = None):
        super().__init__(region)
        # google.cloud.billing.CloudBillingClient when live; None for catalog mode.
        self._billing_client = client

    def get_instance_pricing(
        self,
        instance_type: str,
        pricing_model: PricingModel = PricingModel.ON_DEMAND,
        region: Optional[str] = None,
    ) -> PricingInfo:
        region = region or self.region
        cache_key = f"{instance_type}_{pricing_model.value}_{region}"
        if cache_key in self.pricing_cache:
            return self.pricing_cache[cache_key]

        entry = _GCP_INSTANCE_CATALOG.get(instance_type)
        if entry is None:
            raise ValueError(f"Unknown GCP instance type: {instance_type}")
        multiplier = _GCP_PRICING_MULTIPLIERS.get(pricing_model)
        if multiplier is None:
            raise ValueError(f"Unsupported pricing model for GCP: {pricing_model}")

        price_per_hour = entry["on_demand"] * multiplier
        spec = InstanceSpec(
            provider="gcp",
            instance_type=instance_type,
            vcpus=entry["vcpus"],
            memory_gb=entry["memory_gb"],
            gpu_count=entry.get("gpu_count", 0),
            gpu_type=entry.get("gpu_type"),
            family=entry["family"],
            region=region,
        )
        pricing = PricingInfo(
            instance_spec=spec,
            pricing_model=pricing_model,
            price_per_hour=price_per_hour,
            price_per_month=price_per_hour * 730,
        )
        self.pricing_cache[cache_key] = pricing
        return pricing

    def list_instance_types(
        self,
        family: Optional[InstanceFamily] = None,
        min_vcpus: Optional[int] = None,
        min_memory_gb: Optional[float] = None,
        gpu_required: bool = False,
    ) -> List[InstanceSpec]:
        results: List[InstanceSpec] = []
        for name, entry in _GCP_INSTANCE_CATALOG.items():
            if family is not None and entry["family"] != family:
                continue
            if min_vcpus is not None and entry["vcpus"] < min_vcpus:
                continue
            if min_memory_gb is not None and entry["memory_gb"] < min_memory_gb:
                continue
            if gpu_required and entry.get("gpu_count", 0) == 0:
                continue
            results.append(InstanceSpec(
                provider="gcp",
                instance_type=name,
                vcpus=entry["vcpus"],
                memory_gb=entry["memory_gb"],
                gpu_count=entry.get("gpu_count", 0),
                gpu_type=entry.get("gpu_type"),
                family=entry["family"],
                region=self.region,
            ))
        return results

    def get_storage_pricing(
        self,
        storage_class: str,
        region: Optional[str] = None,
    ) -> StoragePricing:
        entry = _GCP_STORAGE_CATALOG.get(storage_class.upper())
        if entry is None:
            raise ValueError(f"Unknown GCP storage class: {storage_class}")
        return StoragePricing(
            provider="gcp",
            storage_class=storage_class.upper(),
            region=region or self.region,
            price_per_gb_month=entry["price_per_gb_month"],
            retrieval_fee_per_gb=entry["retrieval_fee_per_gb"],
            minimum_storage_duration_days=entry["minimum_days"],
        )

    def get_network_pricing(
        self,
        from_region: str,
        to_region: Optional[str] = None,
        to_internet: bool = False,
    ) -> Dict[str, float]:
        if to_internet:
            return {"egress_per_gb": _GCP_NETWORK_PRICING["internet_egress_per_gb"]}
        if to_region and to_region != from_region:
            return {"egress_per_gb": _GCP_NETWORK_PRICING["inter_region_per_gb"]}
        return {"egress_per_gb": _GCP_NETWORK_PRICING["intra_region_per_gb"]}

    def get_actual_costs(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        if self._billing_client is not None:
            # Live path: depends on the Cloud Billing client and the
            # BigQuery billing-export dataset configured for the account.
            # Implementations vary; this branch is wired by the consumer.
            raise NotImplementedError(
                "Live GCP billing requires a BigQuery billing-export query."
            )
        days = max((end_date - start_date).days, 1)
        per_day = {
            "ComputeEngine": 95.0,
            "CloudStorage": 14.0,
            "CloudSQL": 38.0,
            "Networking": 19.0,
            "Other": 12.0,
        }
        return {key: round(value * days, 2) for key, value in per_day.items()}
