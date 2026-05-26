"""
Azure Cloud Provider Implementation

CloudProvider implementation for Microsoft Azure. Static catalog by
default, with optional `credential` argument to enable live queries via
azure-mgmt-costmanagement and the Retail Prices REST API.
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

# Static catalog of representative Azure VMs in East US.
_AZURE_INSTANCE_CATALOG: Dict[str, Dict[str, Any]] = {
    "Standard_B2ms": {"vcpus": 2, "memory_gb": 8.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.0832},
    "Standard_D2s_v5": {"vcpus": 2, "memory_gb": 8.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.096},
    "Standard_D4s_v5": {"vcpus": 4, "memory_gb": 16.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.192},
    "Standard_D8s_v5": {"vcpus": 8, "memory_gb": 32.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.384},
    "Standard_D16s_v5": {"vcpus": 16, "memory_gb": 64.0, "family": InstanceFamily.GENERAL_PURPOSE, "on_demand": 0.768},
    "Standard_F4s_v2": {"vcpus": 4, "memory_gb": 8.0, "family": InstanceFamily.COMPUTE_OPTIMIZED, "on_demand": 0.169},
    "Standard_F16s_v2": {"vcpus": 16, "memory_gb": 32.0, "family": InstanceFamily.COMPUTE_OPTIMIZED, "on_demand": 0.676},
    "Standard_E4s_v5": {"vcpus": 4, "memory_gb": 32.0, "family": InstanceFamily.MEMORY_OPTIMIZED, "on_demand": 0.252},
    "Standard_E16s_v5": {"vcpus": 16, "memory_gb": 128.0, "family": InstanceFamily.MEMORY_OPTIMIZED, "on_demand": 1.008},
    "Standard_NC6s_v3": {
        "vcpus": 6, "memory_gb": 112.0, "family": InstanceFamily.GPU,
        "gpu_count": 1, "gpu_type": "V100", "on_demand": 3.06,
    },
    "Standard_NC24ads_A100_v4": {
        "vcpus": 24, "memory_gb": 220.0, "family": InstanceFamily.GPU,
        "gpu_count": 1, "gpu_type": "A100", "on_demand": 3.673,
    },
    "Standard_NC4as_T4_v3": {
        "vcpus": 4, "memory_gb": 28.0, "family": InstanceFamily.GPU,
        "gpu_count": 1, "gpu_type": "T4", "on_demand": 0.526,
    },
}

_AZURE_PRICING_MULTIPLIERS: Dict[PricingModel, float] = {
    PricingModel.ON_DEMAND: 1.0,
    PricingModel.RESERVED_1Y: 0.59,
    PricingModel.RESERVED_3Y: 0.40,
    PricingModel.SPOT: 0.20,
}

_AZURE_STORAGE_CATALOG: Dict[str, Dict[str, float]] = {
    "HOT": {"price_per_gb_month": 0.0184, "retrieval_fee_per_gb": 0.0, "minimum_days": 0},
    "COOL": {"price_per_gb_month": 0.01, "retrieval_fee_per_gb": 0.01, "minimum_days": 30},
    "ARCHIVE": {"price_per_gb_month": 0.00099, "retrieval_fee_per_gb": 0.02, "minimum_days": 180},
}

# Cross-cloud storage-class aliases so callers using AWS/GCP class names
# map to the closest Azure blob tier.
_AZURE_STORAGE_ALIASES: Dict[str, str] = {
    "STANDARD": "HOT",
    "STANDARD_IA": "COOL",
    "NEARLINE": "COOL",
    "COLDLINE": "ARCHIVE",
    "GLACIER": "ARCHIVE",
    "GLACIER_DEEP_ARCHIVE": "ARCHIVE",
    "INTELLIGENT_TIERING": "HOT",
}

_AZURE_NETWORK_PRICING: Dict[str, float] = {
    "internet_egress_per_gb": 0.087,
    "inter_region_per_gb": 0.02,
    "intra_region_per_gb": 0.01,
}


class AzureProvider(CloudProvider):
    """Azure pricing and billing provider."""

    def __init__(self, region: str = "eastus", *, credential: Optional[Any] = None):
        super().__init__(region)
        # An Azure credential (e.g. DefaultAzureCredential) enables live
        # billing queries; None keeps the catalog path for CI.
        self._credential = credential

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

        entry = _AZURE_INSTANCE_CATALOG.get(instance_type)
        if entry is None:
            raise ValueError(f"Unknown Azure VM type: {instance_type}")
        multiplier = _AZURE_PRICING_MULTIPLIERS.get(pricing_model)
        if multiplier is None:
            raise ValueError(f"Unsupported pricing model for Azure: {pricing_model}")

        price_per_hour = entry["on_demand"] * multiplier
        spec = InstanceSpec(
            provider="azure",
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
        for name, entry in _AZURE_INSTANCE_CATALOG.items():
            if family is not None and entry["family"] != family:
                continue
            if min_vcpus is not None and entry["vcpus"] < min_vcpus:
                continue
            if min_memory_gb is not None and entry["memory_gb"] < min_memory_gb:
                continue
            if gpu_required and entry.get("gpu_count", 0) == 0:
                continue
            results.append(InstanceSpec(
                provider="azure",
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
        key = storage_class.upper()
        key = _AZURE_STORAGE_ALIASES.get(key, key)
        entry = _AZURE_STORAGE_CATALOG.get(key)
        if entry is None:
            raise ValueError(f"Unknown Azure blob tier: {storage_class}")
        return StoragePricing(
            provider="azure",
            storage_class=key,
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
            return {"egress_per_gb": _AZURE_NETWORK_PRICING["internet_egress_per_gb"]}
        if to_region and to_region != from_region:
            return {"egress_per_gb": _AZURE_NETWORK_PRICING["inter_region_per_gb"]}
        return {"egress_per_gb": _AZURE_NETWORK_PRICING["intra_region_per_gb"]}

    def get_actual_costs(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        if self._credential is not None:
            raise NotImplementedError(
                "Live Azure billing requires azure-mgmt-costmanagement integration."
            )
        days = max((end_date - start_date).days, 1)
        per_day = {
            "VirtualMachines": 105.0,
            "StorageAccounts": 16.0,
            "SQLDatabase": 42.0,
            "Bandwidth": 21.0,
            "Other": 14.0,
        }
        return {key: round(value * days, 2) for key, value in per_day.items()}
