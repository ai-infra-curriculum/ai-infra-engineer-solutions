"""
mlbench - ML Framework Benchmarking Tool

A comprehensive tool for comparing PyTorch, TensorFlow, and JAX performance.
"""

__version__ = "0.1.0"
__author__ = "AI Infrastructure Engineer"

from .framework_interface import FrameworkInterface, BenchmarkResult
from .benchmark_runner import BenchmarkRunner, BenchmarkConfig

__all__ = [
    "FrameworkInterface",
    "BenchmarkResult",
    "BenchmarkRunner",
    "BenchmarkConfig",
]
