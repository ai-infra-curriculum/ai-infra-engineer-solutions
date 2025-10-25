"""Abstract interface for ML frameworks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class BenchmarkResult:
    """Benchmark results for a single run."""

    framework: str
    model_name: str
    device: str
    batch_size: int
    precision: str

    # Training metrics
    train_time_per_epoch: float
    total_train_time: float
    samples_per_second: float

    # Memory metrics
    peak_memory_mb: float
    avg_memory_mb: float

    # Accuracy metrics
    final_train_accuracy: float
    final_val_accuracy: float

    # Model metrics
    num_parameters: int
    model_size_mb: float

    # Inference metrics
    inference_latency_mean_ms: float
    inference_latency_p95_ms: float
    inference_latency_p99_ms: float


class FrameworkInterface(ABC):
    """Abstract interface for ML frameworks."""

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self.model: Any = None

    @abstractmethod
    def build_model(self, model_type: str, **kwargs: Any) -> Any:
        """Build model of specified type."""
        pass

    @abstractmethod
    def train_epoch(
        self, model: Any, train_loader: Any, optimizer: Any, loss_fn: Any
    ) -> Dict[str, float]:
        """Train for one epoch."""
        pass

    @abstractmethod
    def evaluate(self, model: Any, val_loader: Any, loss_fn: Any) -> Dict[str, float]:
        """Evaluate model."""
        pass

    @abstractmethod
    def benchmark_inference(
        self, model: Any, input_shape: Tuple, num_runs: int = 1000
    ) -> Dict[str, float]:
        """Benchmark inference latency."""
        pass

    @abstractmethod
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage."""
        pass

    @abstractmethod
    def count_parameters(self, model: Any) -> int:
        """Count trainable parameters."""
        pass
