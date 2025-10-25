"""
Prometheus metrics for LLM serving and RAG

Tracks:
- Request rates and latencies
- Token usage and throughput
- GPU utilization
- Cost metrics
- RAG performance
"""

import logging
import time
from typing import Dict, Any, Optional
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    generate_latest,
    REGISTRY,
)
import psutil

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    logging.warning("pynvml not available, GPU metrics will not be collected")

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collect and expose Prometheus metrics
    """

    def __init__(self, model_name: str = "llm"):
        """
        Initialize metrics collector

        Args:
            model_name: Name of the model for labeling
        """
        self.model_name = model_name

        # Initialize GPU monitoring if available
        self.gpu_available = False
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_available = True
                self.gpu_count = pynvml.nvmlDeviceGetCount()
                logger.info(f"GPU monitoring initialized ({self.gpu_count} GPUs)")
            except Exception as e:
                logger.warning(f"Failed to initialize GPU monitoring: {e}")

        # Request metrics
        self.request_counter = Counter(
            "llm_requests_total",
            "Total number of LLM requests",
            ["model", "endpoint", "status"],
        )

        self.request_duration = Histogram(
            "llm_request_duration_seconds",
            "LLM request duration in seconds",
            ["model", "endpoint"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )

        self.request_in_progress = Gauge(
            "llm_requests_in_progress",
            "Number of LLM requests currently being processed",
            ["model", "endpoint"],
        )

        # Token metrics
        self.tokens_generated = Counter(
            "llm_tokens_generated_total",
            "Total tokens generated",
            ["model"],
        )

        self.tokens_per_request = Summary(
            "llm_tokens_per_request",
            "Tokens generated per request",
            ["model"],
        )

        self.tokens_per_second = Gauge(
            "llm_tokens_per_second",
            "Current token generation rate",
            ["model"],
        )

        # GPU metrics
        self.gpu_utilization = Gauge(
            "llm_gpu_utilization_percent",
            "GPU utilization percentage",
            ["gpu_id"],
        )

        self.gpu_memory_used = Gauge(
            "llm_gpu_memory_used_bytes",
            "GPU memory used in bytes",
            ["gpu_id"],
        )

        self.gpu_memory_total = Gauge(
            "llm_gpu_memory_total_bytes",
            "Total GPU memory in bytes",
            ["gpu_id"],
        )

        self.gpu_temperature = Gauge(
            "llm_gpu_temperature_celsius",
            "GPU temperature in Celsius",
            ["gpu_id"],
        )

        # Cost metrics
        self.estimated_cost = Counter(
            "llm_estimated_cost_usd",
            "Estimated cost in USD",
            ["model", "cost_type"],
        )

        # RAG metrics
        self.rag_retrievals = Counter(
            "llm_rag_retrievals_total",
            "Total RAG retrievals",
            ["model"],
        )

        self.rag_chunks_retrieved = Summary(
            "llm_rag_chunks_retrieved",
            "Number of chunks retrieved per RAG query",
            ["model"],
        )

        self.rag_retrieval_duration = Histogram(
            "llm_rag_retrieval_duration_seconds",
            "RAG retrieval duration in seconds",
            ["model"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
        )

        # System metrics
        self.cpu_percent = Gauge(
            "llm_cpu_percent",
            "CPU utilization percentage",
        )

        self.memory_used = Gauge(
            "llm_memory_used_bytes",
            "Memory used in bytes",
        )

        # Model info
        self.model_info = Info(
            "llm_model",
            "LLM model information",
        )

    def record_request(
        self,
        endpoint: str,
        duration: float,
        status: str = "success",
        tokens: int = 0,
    ):
        """
        Record a request

        Args:
            endpoint: API endpoint
            duration: Request duration in seconds
            status: Request status (success/error)
            tokens: Tokens generated
        """
        self.request_counter.labels(
            model=self.model_name, endpoint=endpoint, status=status
        ).inc()

        self.request_duration.labels(
            model=self.model_name, endpoint=endpoint
        ).observe(duration)

        if tokens > 0:
            self.tokens_generated.labels(model=self.model_name).inc(tokens)
            self.tokens_per_request.labels(model=self.model_name).observe(tokens)

            # Calculate tokens per second
            if duration > 0:
                tps = tokens / duration
                self.tokens_per_second.labels(model=self.model_name).set(tps)

    def record_rag_retrieval(
        self, num_chunks: int, duration: float
    ):
        """
        Record RAG retrieval

        Args:
            num_chunks: Number of chunks retrieved
            duration: Retrieval duration in seconds
        """
        self.rag_retrievals.labels(model=self.model_name).inc()
        self.rag_chunks_retrieved.labels(model=self.model_name).observe(num_chunks)
        self.rag_retrieval_duration.labels(model=self.model_name).observe(duration)

    def record_cost(
        self, amount: float, cost_type: str = "inference"
    ):
        """
        Record estimated cost

        Args:
            amount: Cost in USD
            cost_type: Type of cost (inference, storage, etc.)
        """
        self.estimated_cost.labels(
            model=self.model_name, cost_type=cost_type
        ).inc(amount)

    def update_gpu_metrics(self):
        """Update GPU metrics"""
        if not self.gpu_available:
            return

        try:
            for i in range(self.gpu_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                # Utilization
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                self.gpu_utilization.labels(gpu_id=str(i)).set(utilization.gpu)

                # Memory
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                self.gpu_memory_used.labels(gpu_id=str(i)).set(memory_info.used)
                self.gpu_memory_total.labels(gpu_id=str(i)).set(memory_info.total)

                # Temperature
                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                    self.gpu_temperature.labels(gpu_id=str(i)).set(temperature)
                except:
                    pass

        except Exception as e:
            logger.error(f"Failed to update GPU metrics: {e}")

    def update_system_metrics(self):
        """Update system metrics"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_percent.set(cpu_percent)

            # Memory
            memory = psutil.virtual_memory()
            self.memory_used.set(memory.used)

        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")

    def set_model_info(self, info: Dict[str, Any]):
        """
        Set model information

        Args:
            info: Model information dict
        """
        # Convert all values to strings
        info_str = {k: str(v) for k, v in info.items()}
        self.model_info.info(info_str)

    def get_metrics(self) -> bytes:
        """
        Get Prometheus metrics in text format

        Returns:
            Metrics in Prometheus text format
        """
        # Update metrics before returning
        self.update_gpu_metrics()
        self.update_system_metrics()

        return generate_latest(REGISTRY)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(model_name: str = "llm") -> MetricsCollector:
    """
    Get global metrics collector instance

    Args:
        model_name: Name of the model

    Returns:
        MetricsCollector instance
    """
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(model_name=model_name)

    return _metrics_collector


class RequestTimer:
    """
    Context manager for timing requests
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        endpoint: str,
    ):
        """
        Initialize timer

        Args:
            metrics_collector: Metrics collector
            endpoint: API endpoint
        """
        self.metrics_collector = metrics_collector
        self.endpoint = endpoint
        self.start_time = None
        self.status = "success"
        self.tokens = 0

    def __enter__(self):
        self.start_time = time.time()
        self.metrics_collector.request_in_progress.labels(
            model=self.metrics_collector.model_name, endpoint=self.endpoint
        ).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        self.metrics_collector.request_in_progress.labels(
            model=self.metrics_collector.model_name, endpoint=self.endpoint
        ).dec()

        if exc_type is not None:
            self.status = "error"

        self.metrics_collector.record_request(
            endpoint=self.endpoint,
            duration=duration,
            status=self.status,
            tokens=self.tokens,
        )

    def set_tokens(self, tokens: int):
        """Set number of tokens generated"""
        self.tokens = tokens
