# Exercise 05: ML Framework Benchmarking Tool

A comprehensive benchmarking tool that compares PyTorch, TensorFlow, and JAX across multiple dimensions including training speed, memory usage, and inference latency.

## Features

- **Multi-Framework Support**: Benchmark PyTorch, TensorFlow, and JAX
- **Comprehensive Metrics**: Training time, throughput, memory usage, inference latency
- **Device Comparison**: CPU vs GPU performance
- **Model Variety**: CNN, Transformer, and MLP architectures
- **Rich Visualizations**: Generate charts and HTML reports
- **Data-Driven Recommendations**: Automatic framework suggestions based on results

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For GPU support, also install CUDA-enabled versions:
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
# pip install tensorflow[and-cuda]
```

### Basic Usage

```bash
# Run quick benchmark (1 epoch, small model)
mlbench run --config configs/quick_test.yaml

# Run comprehensive benchmark
mlbench run --config configs/benchmark_config.yaml

# Benchmark specific frameworks
mlbench run --frameworks pytorch tensorflow

# Generate report from existing results
mlbench report --results results/benchmark_results.json
```

## Project Structure

```
exercise-05-ml-framework-benchmark/
├── src/
│   ├── mlbench/
│   │   ├── __init__.py
│   │   ├── framework_interface.py   # Abstract interface
│   │   ├── pytorch_impl.py          # PyTorch implementation
│   │   ├── tensorflow_impl.py       # TensorFlow implementation
│   │   ├── jax_impl.py              # JAX/Flax implementation
│   │   ├── benchmark_runner.py      # Orchestration
│   │   ├── visualizer.py            # Charts and reports
│   │   └── cli.py                   # CLI interface
├── configs/
│   ├── benchmark_config.yaml        # Default configuration
│   ├── quick_test.yaml              # Fast test config
│   └── comprehensive.yaml           # Full benchmark
├── tests/
│   ├── test_pytorch_impl.py
│   ├── test_tensorflow_impl.py
│   └── test_benchmark_runner.py
├── scripts/
│   ├── setup.sh
│   ├── run.sh
│   └── test.sh
└── README.md
```

## Configuration

Example `benchmark_config.yaml`:

```yaml
frameworks:
  - pytorch
  - tensorflow
  - jax

models:
  - cnn
  - mlp

devices:
  - cpu
  - cuda:0

batch_sizes:
  - 32
  - 64

num_epochs: 5
dataset: cifar10

precision:
  - fp32
```

## Example Output

```
Benchmark Results Summary
┏━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Framework  ┃ Model ┃ Device ┃ Batch Size┃ Time (s)    ┃ Throughput  ┃
┡━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ pytorch    │ cnn   │ cuda:0 │ 32        │ 45.2        │ 1106 samp/s │
│ tensorflow │ cnn   │ cuda:0 │ 32        │ 48.7        │ 1024 samp/s │
│ jax        │ cnn   │ cuda:0 │ 32        │ 42.1        │ 1185 samp/s │
└────────────┴───────┴────────┴───────────┴─────────────┴─────────────┘

Recommendations:
✓ Best for training speed: JAX (42.1s)
✓ Best for inference latency: PyTorch (2.3ms)
✓ Most memory efficient: JAX (1.2GB peak)
```

## Documentation

- [STEP_BY_STEP.md](STEP_BY_STEP.md) - Implementation guide
- [RESULTS.md](docs/RESULTS.md) - Sample benchmark results
- [ANALYSIS.md](docs/ANALYSIS.md) - Framework comparison analysis

## Testing

```bash
# Run all tests
./scripts/test.sh

# Run with coverage
pytest tests/ --cov=src/mlbench --cov-report=html
```

## Requirements

- Python 3.11+
- PyTorch 2.0+
- TensorFlow 2.13+
- JAX 0.4+ with Flax
- CUDA 11.8+ (optional, for GPU benchmarking)

## License

MIT License
