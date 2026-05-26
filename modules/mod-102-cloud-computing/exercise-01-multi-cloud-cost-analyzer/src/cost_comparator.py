"""
Cross-Cloud Cost Comparator

Given a workload spec (instance, storage, network), produce a side-by-side
cost comparison across configured cloud providers. The comparator does not
fetch live pricing itself — it delegates to provider implementations and
focuses on normalization and ranking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .cloud_providers.base import (
    CloudProvider,
    InstanceSpec,
    PricingInfo,
    PricingModel,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkloadSpec:
    """Description of the workload to price across clouds."""

    # Reference instance the user already runs (or wants to size against).
    reference_instance: InstanceSpec
    # Optional storage and network usage; both default to zero.
    storage_gb: float = 0.0
    storage_class: str = "STANDARD"
    monthly_egress_gb: float = 0.0
    pricing_model: PricingModel = PricingModel.ON_DEMAND
    # How many hours per month the instance runs (default = full month).
    hours_per_month: float = 730.0


@dataclass
class ProviderQuote:
    """Quote for one provider for the given workload."""

    provider: str
    instance_pricing: PricingInfo
    storage_monthly_cost: float
    egress_monthly_cost: float
    total_monthly_cost: float
    notes: List[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Comparison output across all providers."""

    workload: WorkloadSpec
    quotes: List[ProviderQuote]
    cheapest_provider: str
    most_expensive_provider: str
    spread_percent: float  # (max - min) / min * 100


class CostComparator:
    """Compare costs across providers for a single workload."""

    def __init__(self, providers: Dict[str, CloudProvider]):
        if not providers:
            raise ValueError("CostComparator requires at least one provider")
        self.providers = providers

    def compare(self, workload: WorkloadSpec) -> ComparisonResult:
        """Produce a quote per provider and rank them."""
        quotes: List[ProviderQuote] = []
        for name, provider in self.providers.items():
            quote = self._quote(name, provider, workload)
            quotes.append(quote)

        if not quotes:
            raise RuntimeError("No quotes produced")

        cheapest = min(quotes, key=lambda q: q.total_monthly_cost)
        most_expensive = max(quotes, key=lambda q: q.total_monthly_cost)
        if cheapest.total_monthly_cost == 0:
            spread = 0.0
        else:
            spread = (
                (most_expensive.total_monthly_cost - cheapest.total_monthly_cost)
                / cheapest.total_monthly_cost
                * 100.0
            )

        return ComparisonResult(
            workload=workload,
            quotes=sorted(quotes, key=lambda q: q.total_monthly_cost),
            cheapest_provider=cheapest.provider,
            most_expensive_provider=most_expensive.provider,
            spread_percent=round(spread, 2),
        )

    def _quote(
        self,
        name: str,
        provider: CloudProvider,
        workload: WorkloadSpec,
    ) -> ProviderQuote:
        notes: List[str] = []
        target = workload.reference_instance

        # If the reference instance is on this provider, price it directly.
        # Otherwise find an equivalent instance.
        if target.provider == name:
            equivalent = target
        else:
            equivalent = provider.find_equivalent_instance(target)
            if equivalent is None:
                notes.append("No equivalent instance found; using on-demand fallback")
                # Pick the cheapest instance that satisfies the family.
                candidates = provider.list_instance_types(family=target.family)
                if not candidates:
                    raise ValueError(
                        f"Provider {name} has no instances matching family {target.family}"
                    )
                # Cheapest among candidates by pricing.
                candidates_with_price = [
                    (c, provider.get_instance_pricing(c.instance_type, workload.pricing_model))
                    for c in candidates
                ]
                equivalent, _ = min(
                    candidates_with_price,
                    key=lambda pair: pair[1].price_per_hour,
                )

        try:
            instance_pricing = provider.get_instance_pricing(
                equivalent.instance_type,
                workload.pricing_model,
            )
        except ValueError as exc:
            # Pricing-model not supported (e.g., PREEMPTIBLE on AWS); fall
            # back to on-demand and annotate the quote.
            notes.append(f"Fallback to on-demand: {exc}")
            instance_pricing = provider.get_instance_pricing(
                equivalent.instance_type,
                PricingModel.ON_DEMAND,
            )

        compute_monthly = instance_pricing.price_per_hour * workload.hours_per_month
        storage_pricing = (
            provider.get_storage_pricing(workload.storage_class)
            if workload.storage_gb > 0
            else None
        )
        storage_monthly = (
            storage_pricing.price_per_gb_month * workload.storage_gb
            if storage_pricing
            else 0.0
        )
        net_pricing = (
            provider.get_network_pricing(provider.region, to_internet=True)
            if workload.monthly_egress_gb > 0
            else None
        )
        egress_monthly = (
            net_pricing["egress_per_gb"] * workload.monthly_egress_gb
            if net_pricing
            else 0.0
        )
        total = compute_monthly + storage_monthly + egress_monthly

        return ProviderQuote(
            provider=name,
            instance_pricing=instance_pricing,
            storage_monthly_cost=round(storage_monthly, 2),
            egress_monthly_cost=round(egress_monthly, 2),
            total_monthly_cost=round(total, 2),
            notes=notes,
        )

    def compare_storage(
        self,
        size_gb: float,
        storage_classes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Compare storage costs per provider for the given size."""
        defaults = {"aws": "STANDARD", "gcp": "STANDARD", "azure": "HOT"}
        classes = storage_classes or defaults
        out: Dict[str, Dict[str, float]] = {}
        for name, provider in self.providers.items():
            sc = classes.get(name, defaults.get(name, "STANDARD"))
            pricing = provider.get_storage_pricing(sc)
            out[name] = {
                "storage_class": sc,
                "monthly_cost": round(pricing.price_per_gb_month * size_gb, 2),
                "price_per_gb_month": pricing.price_per_gb_month,
            }
        return out
