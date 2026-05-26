"""
Cost Optimizer

Given a provider, instance, and usage profile, produce a ranked list of
actionable cost-optimization recommendations. Each recommendation has an
ID, description, estimated monthly savings, and a confidence level. The
ranking puts the highest-impact recommendation first.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .cloud_providers.base import (
    CloudProvider,
    InstanceFamily,
    InstanceSpec,
    PricingModel,
)

logger = logging.getLogger(__name__)


class Confidence(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Recommendation:
    """A single cost-saving recommendation."""

    id: str
    title: str
    description: str
    estimated_monthly_savings_usd: float
    confidence: Confidence
    action: str
    metadata: dict = field(default_factory=dict)


@dataclass
class UsageProfile:
    """Description of how an instance is actually being used."""

    avg_cpu_percent: float = 50.0
    avg_memory_percent: float = 50.0
    avg_gpu_percent: float = 0.0
    monthly_hours: float = 730.0
    interruption_tolerant: bool = False
    commitment_horizon_years: int = 0  # 0 = none, 1, or 3
    age_days: int = 30


class CostOptimizer:
    """Produce optimization recommendations for a specific deployment."""

    # Right-sizing trigger: drop one size if utilization is below this.
    RIGHTSIZE_THRESHOLD = 40.0

    def __init__(self, provider: CloudProvider):
        self.provider = provider

    def recommend(
        self,
        instance: InstanceSpec,
        usage: UsageProfile,
        current_pricing_model: PricingModel = PricingModel.ON_DEMAND,
    ) -> List[Recommendation]:
        """Generate ranked recommendations."""
        recs: List[Recommendation] = []
        recs.extend(self._right_size(instance, usage, current_pricing_model))
        recs.extend(self._reservation(instance, usage, current_pricing_model))
        recs.extend(self._spot(instance, usage, current_pricing_model))
        recs.extend(self._gpu_idle(instance, usage))
        recs.sort(key=lambda r: r.estimated_monthly_savings_usd, reverse=True)
        return recs

    # -- individual checks ---------------------------------------------

    def _right_size(
        self,
        instance: InstanceSpec,
        usage: UsageProfile,
        current_pricing_model: PricingModel,
    ) -> List[Recommendation]:
        bottleneck = max(usage.avg_cpu_percent, usage.avg_memory_percent)
        if bottleneck >= self.RIGHTSIZE_THRESHOLD:
            return []
        # Find the next smaller instance in the same family.
        candidates = self.provider.list_instance_types(family=instance.family)
        smaller = [c for c in candidates if c.vcpus < instance.vcpus and c.vcpus > 0]
        if not smaller:
            return []
        target_vcpus = max(int(instance.vcpus * bottleneck / 100.0), 1)
        # Choose the smallest candidate with vcpus >= target_vcpus.
        candidates_above = sorted(
            (c for c in smaller if c.vcpus >= target_vcpus),
            key=lambda c: c.vcpus,
        )
        target = candidates_above[0] if candidates_above else sorted(smaller, key=lambda c: c.vcpus)[-1]

        current_price = self.provider.get_instance_pricing(
            instance.instance_type, current_pricing_model,
        ).price_per_hour
        target_price = self.provider.get_instance_pricing(
            target.instance_type, current_pricing_model,
        ).price_per_hour
        delta_per_hour = current_price - target_price
        savings = round(max(delta_per_hour, 0.0) * usage.monthly_hours, 2)
        if savings <= 0:
            return []
        return [Recommendation(
            id="rightsize",
            title=f"Right-size {instance.instance_type} → {target.instance_type}",
            description=(
                f"Average utilization is {bottleneck:.0f}% (CPU {usage.avg_cpu_percent:.0f}%, "
                f"memory {usage.avg_memory_percent:.0f}%). Downsizing one tier preserves "
                "headroom while reducing spend."
            ),
            estimated_monthly_savings_usd=savings,
            confidence=Confidence.MEDIUM,
            action=f"Replace {instance.instance_type} with {target.instance_type}.",
            metadata={
                "current_type": instance.instance_type,
                "target_type": target.instance_type,
            },
        )]

    def _reservation(
        self,
        instance: InstanceSpec,
        usage: UsageProfile,
        current_pricing_model: PricingModel,
    ) -> List[Recommendation]:
        if current_pricing_model != PricingModel.ON_DEMAND:
            return []
        if usage.monthly_hours < 700:  # not running essentially full-time
            return []
        # Choose commitment horizon based on age + tolerance.
        if usage.age_days >= 180:
            target_model = PricingModel.RESERVED_3Y
            confidence = Confidence.HIGH
        elif usage.age_days >= 30:
            target_model = PricingModel.RESERVED_1Y
            confidence = Confidence.MEDIUM
        else:
            return []

        try:
            target_price = self.provider.get_instance_pricing(
                instance.instance_type, target_model,
            ).price_per_hour
        except ValueError:
            return []
        current_price = self.provider.get_instance_pricing(
            instance.instance_type, current_pricing_model,
        ).price_per_hour
        savings = round(max(current_price - target_price, 0.0) * usage.monthly_hours, 2)
        if savings <= 0:
            return []
        return [Recommendation(
            id=f"reservation_{target_model.value}",
            title=f"Buy {target_model.value.replace('_', ' ')} reservation",
            description=(
                "Instance has been running steadily; a reservation commitment "
                "would substantially lower the effective rate while preserving "
                "performance characteristics."
            ),
            estimated_monthly_savings_usd=savings,
            confidence=confidence,
            action=f"Purchase a {target_model.value} commitment for {instance.instance_type}.",
            metadata={"target_pricing_model": target_model.value},
        )]

    def _spot(
        self,
        instance: InstanceSpec,
        usage: UsageProfile,
        current_pricing_model: PricingModel,
    ) -> List[Recommendation]:
        if not usage.interruption_tolerant:
            return []
        if current_pricing_model in {PricingModel.SPOT, PricingModel.PREEMPTIBLE}:
            return []
        # Pick spot for AWS/Azure, preemptible for GCP.
        target_model = (
            PricingModel.PREEMPTIBLE if instance.provider == "gcp" else PricingModel.SPOT
        )
        try:
            target_price = self.provider.get_instance_pricing(
                instance.instance_type, target_model,
            ).price_per_hour
        except ValueError:
            return []
        current_price = self.provider.get_instance_pricing(
            instance.instance_type, current_pricing_model,
        ).price_per_hour
        savings = round(max(current_price - target_price, 0.0) * usage.monthly_hours, 2)
        if savings <= 0:
            return []
        return [Recommendation(
            id=f"spot_{target_model.value}",
            title=f"Migrate to {target_model.value.replace('_', ' ')}",
            description=(
                "Workload is marked interruption-tolerant. Spot/preemptible "
                "instances give the largest unit-cost reduction available."
            ),
            estimated_monthly_savings_usd=savings,
            confidence=Confidence.MEDIUM,
            action=f"Run {instance.instance_type} as {target_model.value}.",
            metadata={"target_pricing_model": target_model.value},
        )]

    def _gpu_idle(
        self,
        instance: InstanceSpec,
        usage: UsageProfile,
    ) -> List[Recommendation]:
        if instance.gpu_count == 0:
            return []
        if usage.avg_gpu_percent >= 30.0:
            return []
        # Recommend moving to a non-GPU instance or a smaller GPU.
        current_price = self.provider.get_instance_pricing(
            instance.instance_type, PricingModel.ON_DEMAND,
        ).price_per_hour
        # Pick a general-purpose instance close in CPU/memory.
        cpu_candidates = self.provider.list_instance_types(
            family=InstanceFamily.GENERAL_PURPOSE,
            min_vcpus=instance.vcpus,
            min_memory_gb=instance.memory_gb * 0.5,
        )
        if not cpu_candidates:
            return []
        cpu_candidates_priced = [
            (c, self.provider.get_instance_pricing(c.instance_type, PricingModel.ON_DEMAND))
            for c in cpu_candidates
        ]
        target, target_pricing = min(cpu_candidates_priced, key=lambda pair: pair[1].price_per_hour)
        savings = round(max(current_price - target_pricing.price_per_hour, 0.0) * usage.monthly_hours, 2)
        if savings <= 0:
            return []
        return [Recommendation(
            id="gpu_idle",
            title=f"GPU underutilized: move {instance.instance_type} → {target.instance_type}",
            description=(
                f"GPU utilization averages {usage.avg_gpu_percent:.0f}%. "
                "If the workload doesn't truly need a GPU, switch to a CPU-only "
                "instance. If it does, profile the GPU first to confirm."
            ),
            estimated_monthly_savings_usd=savings,
            confidence=Confidence.LOW,
            action=f"Replace GPU instance with {target.instance_type} after profiling.",
            metadata={
                "current_type": instance.instance_type,
                "target_type": target.instance_type,
            },
        )]
