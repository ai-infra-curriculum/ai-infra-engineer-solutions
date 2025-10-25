"""
Base Cloud Provider Interface

Abstract base class defining the interface for all cloud providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InstanceFamily(Enum):
    """Instance family types"""
    GENERAL_PURPOSE = "general_purpose"
    COMPUTE_OPTIMIZED = "compute_optimized"
    MEMORY_OPTIMIZED = "memory_optimized"
    GPU = "gpu"
    STORAGE_OPTIMIZED = "storage_optimized"


class PricingModel(Enum):
    """Pricing models"""
    ON_DEMAND = "on_demand"
    RESERVED_1Y = "reserved_1y"
    RESERVED_3Y = "reserved_3y"
    SPOT = "spot"
    PREEMPTIBLE = "preemptible"


@dataclass
class InstanceSpec:
    """Cloud instance specification"""
    provider: str
    instance_type: str
    vcpus: int
    memory_gb: float
    gpu_count: int = 0
    gpu_type: Optional[str] = None
    family: InstanceFamily = InstanceFamily.GENERAL_PURPOSE
    region: str = "us-east-1"

    def matches(self, other: 'InstanceSpec', tolerance: float = 0.25) -> bool:
        """Check if this instance spec matches another within tolerance"""
        if self.gpu_count > 0 or other.gpu_count > 0:
            if self.gpu_count != other.gpu_count or self.gpu_type != other.gpu_type:
                return False

        vcpu_diff = abs(self.vcpus - other.vcpus) / max(self.vcpus, other.vcpus)
        mem_diff = abs(self.memory_gb - other.memory_gb) / max(self.memory_gb, other.memory_gb)

        return vcpu_diff <= tolerance and mem_diff <= tolerance


@dataclass
class PricingInfo:
    """Instance pricing information"""
    instance_spec: InstanceSpec
    pricing_model: PricingModel
    price_per_hour: float
    price_per_month: float
    currency: str = "USD"
    effective_date: datetime = None

    def __post_init__(self):
        if self.effective_date is None:
            self.effective_date = datetime.now()


@dataclass
class StoragePricing:
    """Storage pricing"""
    provider: str
    storage_class: str
    region: str
    price_per_gb_month: float
    retrieval_fee_per_gb: Optional[float] = None
    minimum_storage_duration_days: int = 0


class CloudProvider(ABC):
    """Abstract base class for cloud providers"""

    def __init__(self, region: str = None):
        self.region = region
        self.pricing_cache = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def get_instance_pricing(
        self,
        instance_type: str,
        pricing_model: PricingModel = PricingModel.ON_DEMAND,
        region: Optional[str] = None
    ) -> PricingInfo:
        """Get pricing for specific instance type"""
        pass

    @abstractmethod
    def list_instance_types(
        self,
        family: Optional[InstanceFamily] = None,
        min_vcpus: Optional[int] = None,
        min_memory_gb: Optional[float] = None,
        gpu_required: bool = False
    ) -> List[InstanceSpec]:
        """List available instance types matching criteria"""
        pass

    @abstractmethod
    def get_storage_pricing(
        self,
        storage_class: str,
        region: Optional[str] = None
    ) -> StoragePricing:
        """Get storage pricing"""
        pass

    @abstractmethod
    def get_network_pricing(
        self,
        from_region: str,
        to_region: Optional[str] = None,
        to_internet: bool = False
    ) -> Dict[str, float]:
        """Get network/egress pricing"""
        pass

    @abstractmethod
    def get_actual_costs(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Get actual spending from billing API"""
        pass

    def find_equivalent_instance(
        self,
        target_spec: InstanceSpec,
        tolerance: float = 0.25
    ) -> Optional[InstanceSpec]:
        """Find equivalent instance on this cloud provider"""
        self.logger.debug(f"Finding equivalent for {target_spec.instance_type}")

        instances = self.list_instance_types(
            family=target_spec.family,
            min_vcpus=int(target_spec.vcpus * (1 - tolerance)),
            min_memory_gb=target_spec.memory_gb * (1 - tolerance),
            gpu_required=target_spec.gpu_count > 0
        )

        best_match = None
        best_score = float('inf')

        for instance in instances:
            if instance.matches(target_spec, tolerance):
                vcpu_diff = abs(instance.vcpus - target_spec.vcpus)
                mem_diff = abs(instance.memory_gb - target_spec.memory_gb)
                score = vcpu_diff + mem_diff

                if score < best_score:
                    best_score = score
                    best_match = instance

        return best_match
