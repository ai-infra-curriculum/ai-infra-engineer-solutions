"""
Cost tracking and estimation for LLM operations

Tracks:
- GPU compute costs
- API call costs
- Storage costs
- Total operational costs
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CostConfig:
    """Cost configuration"""

    # GPU costs (per hour)
    gpu_cost_per_hour: float = 1.0  # Default: $1/hour (e.g., T4 spot instance)

    # Storage costs (per GB per month)
    storage_cost_per_gb_month: float = 0.10

    # Vector DB costs (if using managed service)
    vector_db_cost_per_query: float = 0.0001
    vector_db_cost_per_gb_month: float = 0.25

    # Network costs (per GB)
    network_cost_per_gb: float = 0.12

    # Model-specific token costs (for external APIs)
    cost_per_1k_tokens: float = 0.0  # $0 for self-hosted


@dataclass
class CostMetrics:
    """Cost metrics over time period"""

    gpu_cost: float = 0.0
    storage_cost: float = 0.0
    vector_db_cost: float = 0.0
    network_cost: float = 0.0
    total_cost: float = 0.0

    num_requests: int = 0
    total_tokens: int = 0

    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    def cost_per_request(self) -> float:
        """Calculate cost per request"""
        if self.num_requests == 0:
            return 0.0
        return self.total_cost / self.num_requests

    def cost_per_1k_tokens(self) -> float:
        """Calculate cost per 1k tokens"""
        if self.total_tokens == 0:
            return 0.0
        return (self.total_cost / self.total_tokens) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "gpu_cost": self.gpu_cost,
            "storage_cost": self.storage_cost,
            "vector_db_cost": self.vector_db_cost,
            "network_cost": self.network_cost,
            "total_cost": self.total_cost,
            "num_requests": self.num_requests,
            "total_tokens": self.total_tokens,
            "cost_per_request": self.cost_per_request(),
            "cost_per_1k_tokens": self.cost_per_1k_tokens(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class CostTracker:
    """
    Track and estimate costs for LLM operations
    """

    def __init__(
        self,
        config: Optional[CostConfig] = None,
        persist_file: Optional[str] = None,
    ):
        """
        Initialize cost tracker

        Args:
            config: Cost configuration
            persist_file: File to persist cost data
        """
        self.config = config or CostConfig()
        self.persist_file = persist_file

        # Current period metrics
        self.current_metrics = CostMetrics()

        # Historical metrics by period
        self.hourly_metrics: Dict[str, CostMetrics] = {}
        self.daily_metrics: Dict[str, CostMetrics] = {}

        # GPU uptime tracking
        self.gpu_start_time = datetime.now()

        # Load persisted data
        if persist_file:
            self.load()

        logger.info("Cost tracker initialized")

    def record_request(
        self,
        tokens: int = 0,
        duration: float = 0.0,
        vector_db_queries: int = 0,
        data_transferred_gb: float = 0.0,
    ):
        """
        Record a request and its costs

        Args:
            tokens: Number of tokens generated
            duration: Request duration in seconds
            vector_db_queries: Number of vector DB queries
            data_transferred_gb: Data transferred in GB
        """
        # Calculate costs
        gpu_cost = self._calculate_gpu_cost(duration)
        vector_db_cost = vector_db_queries * self.config.vector_db_cost_per_query
        network_cost = data_transferred_gb * self.config.network_cost_per_gb
        token_cost = (tokens / 1000) * self.config.cost_per_1k_tokens

        total_cost = gpu_cost + vector_db_cost + network_cost + token_cost

        # Update current metrics
        self.current_metrics.gpu_cost += gpu_cost
        self.current_metrics.vector_db_cost += vector_db_cost
        self.current_metrics.network_cost += network_cost
        self.current_metrics.total_cost += total_cost
        self.current_metrics.num_requests += 1
        self.current_metrics.total_tokens += tokens

        # Update periodic metrics
        self._update_periodic_metrics(
            gpu_cost, vector_db_cost, network_cost, total_cost, tokens
        )

        logger.debug(
            f"Recorded request cost: ${total_cost:.6f} "
            f"(GPU: ${gpu_cost:.6f}, VectorDB: ${vector_db_cost:.6f}, "
            f"Network: ${network_cost:.6f}, Tokens: {tokens})"
        )

    def _calculate_gpu_cost(self, duration: float) -> float:
        """
        Calculate GPU cost for duration

        Args:
            duration: Duration in seconds

        Returns:
            Cost in USD
        """
        hours = duration / 3600.0
        return hours * self.config.gpu_cost_per_hour

    def _update_periodic_metrics(
        self,
        gpu_cost: float,
        vector_db_cost: float,
        network_cost: float,
        total_cost: float,
        tokens: int,
    ):
        """Update hourly and daily metrics"""
        now = datetime.now()

        # Hourly metrics
        hour_key = now.strftime("%Y-%m-%d-%H")
        if hour_key not in self.hourly_metrics:
            self.hourly_metrics[hour_key] = CostMetrics(start_time=now)

        hourly = self.hourly_metrics[hour_key]
        hourly.gpu_cost += gpu_cost
        hourly.vector_db_cost += vector_db_cost
        hourly.network_cost += network_cost
        hourly.total_cost += total_cost
        hourly.num_requests += 1
        hourly.total_tokens += tokens
        hourly.end_time = now

        # Daily metrics
        day_key = now.strftime("%Y-%m-%d")
        if day_key not in self.daily_metrics:
            self.daily_metrics[day_key] = CostMetrics(start_time=now)

        daily = self.daily_metrics[day_key]
        daily.gpu_cost += gpu_cost
        daily.vector_db_cost += vector_db_cost
        daily.network_cost += network_cost
        daily.total_cost += total_cost
        daily.num_requests += 1
        daily.total_tokens += tokens
        daily.end_time = now

        # Clean old metrics (keep last 30 days)
        self._cleanup_old_metrics()

    def _cleanup_old_metrics(self, days_to_keep: int = 30):
        """Remove metrics older than specified days"""
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        # Clean daily metrics
        self.daily_metrics = {
            k: v for k, v in self.daily_metrics.items() if k >= cutoff_str
        }

        # Clean hourly metrics (keep last 7 days)
        cutoff_hour = datetime.now() - timedelta(days=7)
        cutoff_hour_str = cutoff_hour.strftime("%Y-%m-%d-%H")

        self.hourly_metrics = {
            k: v for k, v in self.hourly_metrics.items() if k >= cutoff_hour_str
        }

    def get_current_metrics(self) -> CostMetrics:
        """Get current period metrics"""
        return self.current_metrics

    def get_hourly_metrics(self, hours: int = 24) -> Dict[str, CostMetrics]:
        """
        Get hourly metrics for last N hours

        Args:
            hours: Number of hours to retrieve

        Returns:
            Dictionary of hourly metrics
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%d-%H")

        return {k: v for k, v in self.hourly_metrics.items() if k >= cutoff_str}

    def get_daily_metrics(self, days: int = 30) -> Dict[str, CostMetrics]:
        """
        Get daily metrics for last N days

        Args:
            days: Number of days to retrieve

        Returns:
            Dictionary of daily metrics
        """
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        return {k: v for k, v in self.daily_metrics.items() if k >= cutoff_str}

    def estimate_monthly_cost(self) -> float:
        """
        Estimate monthly cost based on recent usage

        Returns:
            Estimated monthly cost in USD
        """
        # Use last 7 days for estimation
        daily_metrics = self.get_daily_metrics(days=7)

        if not daily_metrics:
            return 0.0

        # Calculate average daily cost
        total_cost = sum(m.total_cost for m in daily_metrics.values())
        avg_daily_cost = total_cost / len(daily_metrics)

        # Estimate monthly (30 days)
        estimated_monthly = avg_daily_cost * 30

        # Add fixed costs (storage, etc.)
        # Assuming 100GB storage
        storage_monthly = 100 * self.config.storage_cost_per_gb_month

        return estimated_monthly + storage_monthly

    def get_cost_breakdown(self) -> Dict[str, Any]:
        """
        Get detailed cost breakdown

        Returns:
            Cost breakdown dictionary
        """
        current = self.current_metrics

        return {
            "current_period": current.to_dict(),
            "cost_breakdown": {
                "gpu": {
                    "cost": current.gpu_cost,
                    "percentage": (
                        (current.gpu_cost / current.total_cost * 100)
                        if current.total_cost > 0
                        else 0
                    ),
                },
                "vector_db": {
                    "cost": current.vector_db_cost,
                    "percentage": (
                        (current.vector_db_cost / current.total_cost * 100)
                        if current.total_cost > 0
                        else 0
                    ),
                },
                "network": {
                    "cost": current.network_cost,
                    "percentage": (
                        (current.network_cost / current.total_cost * 100)
                        if current.total_cost > 0
                        else 0
                    ),
                },
            },
            "estimated_monthly": self.estimate_monthly_cost(),
            "config": {
                "gpu_cost_per_hour": self.config.gpu_cost_per_hour,
                "storage_cost_per_gb_month": self.config.storage_cost_per_gb_month,
                "vector_db_cost_per_query": self.config.vector_db_cost_per_query,
            },
        }

    def get_optimization_recommendations(self) -> list:
        """
        Get cost optimization recommendations

        Returns:
            List of recommendations
        """
        recommendations = []
        breakdown = self.get_cost_breakdown()

        # GPU optimization
        gpu_pct = breakdown["cost_breakdown"]["gpu"]["percentage"]
        if gpu_pct > 70:
            recommendations.append({
                "category": "GPU",
                "priority": "high",
                "recommendation": "GPU costs are high (>70%). Consider: "
                "1) Model quantization to use smaller GPU "
                "2) Request batching to improve utilization "
                "3) Auto-scaling to reduce idle time",
            })

        # Vector DB optimization
        vdb_pct = breakdown["cost_breakdown"]["vector_db"]["percentage"]
        if vdb_pct > 20:
            recommendations.append({
                "category": "Vector Database",
                "priority": "medium",
                "recommendation": "Vector DB costs are high (>20%). Consider: "
                "1) Self-hosted ChromaDB instead of managed service "
                "2) Caching frequent queries "
                "3) Optimizing retrieval parameters (reduce top_k)",
            })

        # Monthly cost warning
        monthly_estimate = breakdown["estimated_monthly"]
        if monthly_estimate > 500:
            recommendations.append({
                "category": "Overall",
                "priority": "high",
                "recommendation": f"Estimated monthly cost is ${monthly_estimate:.2f}. "
                "Consider spot instances, reserved instances, or auto-scaling.",
            })

        return recommendations

    def save(self):
        """Save cost data to file"""
        if not self.persist_file:
            return

        data = {
            "current_metrics": self.current_metrics.to_dict(),
            "hourly_metrics": {
                k: v.to_dict() for k, v in self.hourly_metrics.items()
            },
            "daily_metrics": {k: v.to_dict() for k, v in self.daily_metrics.items()},
            "config": {
                "gpu_cost_per_hour": self.config.gpu_cost_per_hour,
                "storage_cost_per_gb_month": self.config.storage_cost_per_gb_month,
                "vector_db_cost_per_query": self.config.vector_db_cost_per_query,
            },
        }

        with open(self.persist_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved cost data to {self.persist_file}")

    def load(self):
        """Load cost data from file"""
        if not self.persist_file or not Path(self.persist_file).exists():
            return

        try:
            with open(self.persist_file, "r") as f:
                data = json.load(f)

            # Load config
            if "config" in data:
                config_data = data["config"]
                self.config = CostConfig(**config_data)

            logger.info(f"Loaded cost data from {self.persist_file}")

        except Exception as e:
            logger.error(f"Failed to load cost data: {e}")
