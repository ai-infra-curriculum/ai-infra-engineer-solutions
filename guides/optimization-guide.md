# AI Infrastructure Optimization Guide

> **A comprehensive guide to optimizing AI infrastructure systems for performance, cost, and resource efficiency**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Optimization Principles](#optimization-principles)
3. [Code-Level Optimizations](#code-level-optimizations)
   - [Python Performance](#python-performance)
   - [Async and Concurrency](#async-and-concurrency)
   - [Caching Strategies](#caching-strategies)
4. [ML Model Optimizations](#ml-model-optimizations)
   - [Model Quantization](#model-quantization)
   - [Model Pruning](#model-pruning)
   - [Batching and Throughput](#batching-and-throughput)
   - [GPU Utilization](#gpu-utilization)
5. [Docker Optimizations](#docker-optimizations)
   - [Image Size Reduction](#image-size-reduction)
   - [Build Cache](#build-cache)
   - [Multi-Stage Builds](#multi-stage-builds)
6. [Kubernetes Optimizations](#kubernetes-optimizations)
   - [Resource Management](#resource-management)
   - [Autoscaling](#autoscaling)
   - [Pod Disruption Budgets](#pod-disruption-budgets)
   - [Network Performance](#network-performance)
7. [Database Optimizations](#database-optimizations)
   - [Query Optimization](#query-optimization)
   - [Indexing Strategies](#indexing-strategies)
   - [Connection Pooling](#connection-pooling)
8. [Network Optimizations](#network-optimizations)
   - [Compression](#compression)
   - [CDN and Caching](#cdn-and-caching)
   - [HTTP/2 and gRPC](#http2-and-grpc)
9. [Cost Optimization](#cost-optimization)
   - [Resource Right-Sizing](#resource-right-sizing)
   - [Spot Instances](#spot-instances)
   - [Reserved Capacity](#reserved-capacity)
10. [Monitoring and Profiling](#monitoring-and-profiling)
11. [Project-Specific Optimizations](#project-specific-optimizations)
    - [Project 01: Model Serving API](#project-01-model-serving-api-optimizations)
    - [Project 02: Multi-Model Serving](#project-02-multi-model-serving-optimizations)
    - [Project 03: GPU-Accelerated Inference](#project-03-gpu-accelerated-inference-optimizations)
12. [Benchmarking Methodologies](#benchmarking-methodologies)
13. [Real-World Optimization Case Studies](#real-world-optimization-case-studies)
14. [Optimization Checklists](#optimization-checklists)
15. [Resources and References](#resources-and-references)

---

## Introduction

### What is Optimization?

Optimization is the process of improving system performance across multiple dimensions:

- **Performance**: Reduce latency, increase throughput
- **Resource Efficiency**: Use less CPU, memory, disk, network
- **Cost**: Reduce infrastructure spend
- **User Experience**: Faster responses, higher availability
- **Scalability**: Handle more load with same resources

### The Optimization Mindset

```
┌─────────────────────────────────────────────────┐
│          MEASURE → ANALYZE → OPTIMIZE           │
│               ↑                    ↓             │
│               └────── VERIFY ──────┘             │
└─────────────────────────────────────────────────┘

1. MEASURE: Establish baseline metrics
2. ANALYZE: Identify bottlenecks
3. OPTIMIZE: Apply targeted improvements
4. VERIFY: Measure impact
5. REPEAT: Continuous improvement
```

### Optimization Priorities

**Pareto Principle (80/20 Rule):**
- 80% of performance impact comes from 20% of code
- Focus on the hot path
- Profile before optimizing

**Priority Framework:**

```
High Impact, Low Effort  →  DO FIRST
High Impact, High Effort →  PLAN CAREFULLY
Low Impact, Low Effort   →  NICE TO HAVE
Low Impact, High Effort  →  AVOID
```

---

## Optimization Principles

### 1. Measure Before Optimizing

**Never guess, always measure:**

```python
import time
import functools

def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed*1000:.2f}ms")
        return result
    return wrapper

@timer
def process_data(data):
    # Your code here
    return result
```

### 2. Profile to Find Bottlenecks

**CPU Profiling:**

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code
result = expensive_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

**Memory Profiling:**

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    large_list = [i for i in range(10**7)]
    return sum(large_list)
```

### 3. Optimize the Hot Path

**Identify critical code paths:**

```python
# Bad: Optimize everything equally
def process_request(data):
    optimized_validation(data)      # Used rarely
    optimized_transformation(data)  # Used rarely
    optimized_inference(data)       # Used always ← Hot path

# Good: Focus on hot path
def process_request(data):
    simple_validation(data)        # Simple is fine
    simple_transformation(data)    # Simple is fine
    highly_optimized_inference(data)  # Optimize this!
```

### 4. Choose the Right Algorithm

**Algorithmic complexity matters more than micro-optimizations:**

```python
# O(n²) - Bad for large datasets
def find_duplicates_slow(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            if items[i] == items[j]:
                duplicates.append(items[i])
    return duplicates

# O(n) - Much better
def find_duplicates_fast(items):
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return list(duplicates)

# Benchmark:
# 1000 items: 0.5ms vs 50ms (100x faster)
# 10000 items: 5ms vs 5000ms (1000x faster)
```

### 5. Trade-offs Are Inevitable

**Common trade-offs:**

| Optimization | Benefit | Cost |
|--------------|---------|------|
| Caching | Faster reads | Memory usage, cache invalidation complexity |
| Batching | Higher throughput | Higher latency per request |
| Compression | Less network/disk | More CPU usage |
| Denormalization | Faster queries | Data duplication, consistency challenges |
| Async I/O | Better concurrency | Code complexity |

---

## Code-Level Optimizations

### Python Performance

#### Use Built-in Functions and Libraries

```python
import numpy as np

# Bad: Pure Python loops
def sum_squares_slow(n):
    total = 0
    for i in range(n):
        total += i * i
    return total

# Good: Built-in sum with generator
def sum_squares_medium(n):
    return sum(i * i for i in range(n))

# Best: NumPy vectorization
def sum_squares_fast(n):
    arr = np.arange(n)
    return np.sum(arr * arr)

# Benchmark (n=1,000,000):
# Pure Python:  180ms
# Built-in:     120ms
# NumPy:        5ms (36x faster!)
```

#### List Comprehensions vs Loops

```python
# Bad: Append in loop
result = []
for i in range(1000):
    if i % 2 == 0:
        result.append(i * 2)

# Good: List comprehension
result = [i * 2 for i in range(1000) if i % 2 == 0]

# Benchmark:
# Loop:       120μs
# Comprehension: 70μs (1.7x faster)
```

#### Use Local Variables

```python
import math

# Bad: Lookup in each iteration
def slow_calculation(items):
    result = []
    for item in items:
        result.append(math.sqrt(item))  # Global lookup each time
    return result

# Good: Cache in local variable
def fast_calculation(items):
    sqrt = math.sqrt  # Local variable
    result = []
    for item in items:
        result.append(sqrt(item))
    return result

# Benchmark (10,000 items):
# Slow: 2.5ms
# Fast: 1.8ms (1.4x faster)
```

#### Avoid String Concatenation in Loops

```python
# Bad: String concatenation
def build_string_slow(items):
    result = ""
    for item in items:
        result += str(item) + ","
    return result

# Good: Join list
def build_string_fast(items):
    return ",".join(str(item) for item in items)

# Benchmark (1,000 items):
# Slow: 15ms
# Fast: 0.5ms (30x faster!)
```

#### Use Generators for Large Datasets

```python
# Bad: Load everything into memory
def process_all_at_once(filename):
    with open(filename) as f:
        lines = f.readlines()  # Load entire file
        return [process_line(line) for line in lines]

# Good: Process one at a time
def process_generator(filename):
    with open(filename) as f:
        for line in f:  # Generator
            yield process_line(line)

# Memory usage:
# All at once: 500MB for 10GB file
# Generator:   ~10KB regardless of file size
```

#### Use `__slots__` for Classes

```python
# Bad: Regular class
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# Good: Use __slots__
class PointOptimized:
    __slots__ = ['x', 'y']

    def __init__(self, x, y):
        self.x = x
        self.y = y

# Memory comparison (1,000,000 instances):
# Regular:    152 MB
# Slots:      64 MB (2.4x less memory)
# Access:     ~15% faster
```

### Async and Concurrency

#### Async I/O for Network Operations

```python
import asyncio
import aiohttp
import time

# Bad: Sequential requests
def fetch_all_sequential(urls):
    results = []
    for url in urls:
        response = requests.get(url)
        results.append(response.json())
    return results

# Good: Async concurrent requests
async def fetch_all_async(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks)

async def fetch_one(session, url):
    async with session.get(url) as response:
        return await response.json()

# Benchmark (10 URLs, 100ms each):
# Sequential: 1000ms
# Async:      100ms (10x faster)
```

#### Thread Pool for CPU-Bound Tasks

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import numpy as np

# For I/O-bound tasks
def process_io_bound(items):
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(download_item, items))
    return results

# For CPU-bound tasks (releases GIL)
def process_cpu_bound(items):
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(cpu_intensive_task, items))
    return results

# Example CPU-intensive task
def cpu_intensive_task(data):
    # NumPy operations release GIL
    return np.fft.fft(data)
```

#### AsyncIO for ML Inference

```python
import asyncio
from typing import List
import torch

class AsyncModelServer:
    def __init__(self, model, batch_size=32, wait_time=0.01):
        self.model = model
        self.batch_size = batch_size
        self.wait_time = wait_time
        self.queue = asyncio.Queue()
        self.results = {}

    async def predict(self, request_id: str, data: torch.Tensor):
        # Add to queue
        future = asyncio.Future()
        await self.queue.put((request_id, data, future))

        # Wait for result
        result = await future
        return result

    async def batch_processor(self):
        while True:
            # Collect batch
            batch = []
            for _ in range(self.batch_size):
                try:
                    item = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=self.wait_time
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    break

            if not batch:
                await asyncio.sleep(0.001)
                continue

            # Process batch
            request_ids, inputs, futures = zip(*batch)
            inputs_tensor = torch.stack(inputs)

            with torch.no_grad():
                outputs = self.model(inputs_tensor)

            # Return results
            for request_id, output, future in zip(request_ids, outputs, futures):
                future.set_result(output)

# Usage
server = AsyncModelServer(model)
asyncio.create_task(server.batch_processor())

# Concurrent requests
results = await asyncio.gather(*[
    server.predict(f"req-{i}", data)
    for i in range(100)
])

# Benefit:
# Single requests: 100 * 10ms = 1000ms
# Batched async:   100 / 32 * 50ms = 156ms (6.4x faster)
```

### Caching Strategies

#### LRU Cache for Function Results

```python
from functools import lru_cache

# Without cache
def fibonacci_slow(n):
    if n < 2:
        return n
    return fibonacci_slow(n-1) + fibonacci_slow(n-2)

# With cache
@lru_cache(maxsize=128)
def fibonacci_fast(n):
    if n < 2:
        return n
    return fibonacci_fast(n-1) + fibonacci_fast(n-2)

# Benchmark:
# fibonacci_slow(35):  ~5 seconds
# fibonacci_fast(35):  <1 millisecond
```

#### Custom Cache with TTL

```python
import time
from typing import Any, Optional

class TTLCache:
    def __init__(self, ttl_seconds=300, maxsize=1000):
        self.ttl_seconds = ttl_seconds
        self.maxsize = maxsize
        self.cache = {}
        self.access_times = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None

        # Check if expired
        if time.time() - self.access_times[key] > self.ttl_seconds:
            del self.cache[key]
            del self.access_times[key]
            return None

        self.access_times[key] = time.time()
        return self.cache[key]

    def put(self, key: str, value: Any):
        # Evict oldest if at capacity
        if len(self.cache) >= self.maxsize:
            oldest_key = min(self.access_times, key=self.access_times.get)
            del self.cache[oldest_key]
            del self.access_times[oldest_key]

        self.cache[key] = value
        self.access_times[key] = time.time()

# Usage
cache = TTLCache(ttl_seconds=60, maxsize=1000)

def get_prediction(input_hash: str, data):
    # Check cache
    cached = cache.get(input_hash)
    if cached is not None:
        return cached

    # Compute and cache
    result = model.predict(data)
    cache.put(input_hash, result)
    return result
```

#### Redis-Based Distributed Cache

```python
import redis
import json
import hashlib

class RedisCache:
    def __init__(self, host='localhost', port=6379, ttl=300):
        self.client = redis.Redis(host=host, port=port, decode_responses=True)
        self.ttl = ttl

    def get(self, key: str):
        value = self.client.get(key)
        if value:
            return json.loads(value)
        return None

    def put(self, key: str, value):
        self.client.setex(
            key,
            self.ttl,
            json.dumps(value)
        )

    def invalidate(self, pattern: str):
        """Invalidate keys matching pattern"""
        keys = self.client.keys(pattern)
        if keys:
            self.client.delete(*keys)

# Usage
cache = RedisCache(ttl=300)

def predict_with_cache(model_id: str, input_data):
    # Create cache key
    data_hash = hashlib.md5(
        str(input_data).encode()
    ).hexdigest()
    cache_key = f"prediction:{model_id}:{data_hash}"

    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Compute and cache
    result = model.predict(input_data)
    cache.put(cache_key, result)
    return result

# Cache invalidation on model update
def update_model(model_id: str, new_model):
    global model
    model = new_model
    # Invalidate all predictions for this model
    cache.invalidate(f"prediction:{model_id}:*")
```

---

## ML Model Optimizations

### Model Quantization

**Reduce model precision from FP32 to INT8:**

```python
import torch

# Original FP32 model
model = load_model()  # 100MB, FP32

# Dynamic quantization (easiest)
quantized_model = torch.quantization.quantize_dynamic(
    model,
    {torch.nn.Linear},  # Layers to quantize
    dtype=torch.qint8
)
# Result: 25MB, 2-4x faster inference

# Static quantization (better accuracy)
model_fp32 = load_model()
model_fp32.eval()

# Prepare for quantization
model_fp32.qconfig = torch.quantization.get_default_qconfig('fbgemm')
torch.quantization.prepare(model_fp32, inplace=True)

# Calibrate with representative data
with torch.no_grad():
    for data in calibration_dataloader:
        model_fp32(data)

# Convert to quantized model
model_int8 = torch.quantization.convert(model_fp32, inplace=False)

# Quantization-aware training (best accuracy)
model.qconfig = torch.quantization.get_default_qat_qconfig('fbgemm')
model_prepared = torch.quantization.prepare_qat(model, inplace=False)

# Train with quantization
for epoch in range(num_epochs):
    train_one_epoch(model_prepared)

model_quantized = torch.quantization.convert(model_prepared, inplace=False)

# Benchmark comparison:
# FP32:  100ms, 100MB
# INT8:  25ms,  25MB  (4x faster, 4x smaller)
```

### Model Pruning

**Remove unnecessary weights:**

```python
import torch
import torch.nn.utils.prune as prune

model = load_model()

# Prune individual layer
module = model.conv1
prune.l1_unstructured(module, name='weight', amount=0.3)  # Remove 30% of weights

# Prune multiple layers
parameters_to_prune = []
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Conv2d):
        parameters_to_prune.append((module, 'weight'))

prune.global_unstructured(
    parameters_to_prune,
    pruning_method=prune.L1Unstructured,
    amount=0.3,
)

# Make pruning permanent
for module, _ in parameters_to_prune:
    prune.remove(module, 'weight')

# Fine-tune pruned model
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
for epoch in range(fine_tune_epochs):
    train_one_epoch(model, optimizer)

# Result:
# Original: 50M parameters, 100ms inference
# Pruned:   35M parameters, 70ms inference (30% reduction)
```

### Batching and Throughput

#### Dynamic Batching

```python
import asyncio
import torch
from collections import deque
from typing import List, Tuple

class DynamicBatcher:
    def __init__(
        self,
        model,
        max_batch_size=32,
        max_wait_time=0.01  # 10ms
    ):
        self.model = model
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.queue = asyncio.Queue()

    async def predict(self, data: torch.Tensor):
        """Submit prediction request"""
        future = asyncio.Future()
        await self.queue.put((data, future))
        return await future

    async def process_batches(self):
        """Background task to process batches"""
        while True:
            batch = await self._collect_batch()
            if batch:
                await self._process_batch(batch)

    async def _collect_batch(self) -> List[Tuple]:
        """Collect requests into a batch"""
        batch = []
        deadline = asyncio.get_event_loop().time() + self.max_wait_time

        while len(batch) < self.max_batch_size:
            timeout = max(0, deadline - asyncio.get_event_loop().time())
            try:
                item = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=timeout
                )
                batch.append(item)
            except asyncio.TimeoutError:
                break

        return batch

    async def _process_batch(self, batch: List[Tuple]):
        """Process a batch of requests"""
        if not batch:
            return

        # Separate data and futures
        data_list, futures = zip(*batch)

        # Stack into batch tensor
        batch_tensor = torch.stack(data_list)

        # Run inference
        with torch.no_grad():
            results = self.model(batch_tensor)

        # Return results to futures
        for future, result in zip(futures, results):
            future.set_result(result)

# Usage
batcher = DynamicBatcher(model, max_batch_size=32, max_wait_time=0.01)

# Start background processor
asyncio.create_task(batcher.process_batches())

# Submit requests
results = await asyncio.gather(*[
    batcher.predict(input_data)
    for input_data in requests
])

# Performance:
# Individual requests: 100 req/s, 10ms latency
# Dynamic batching:    800 req/s, 15ms latency (8x throughput)
```

#### Adaptive Batch Sizing

```python
class AdaptiveBatcher:
    def __init__(self, model, initial_batch_size=16):
        self.model = model
        self.batch_size = initial_batch_size
        self.latencies = deque(maxlen=100)
        self.throughputs = deque(maxlen=100)

    def adjust_batch_size(self):
        """Adjust batch size based on recent performance"""
        if len(self.latencies) < 10:
            return

        avg_latency = sum(self.latencies) / len(self.latencies)
        avg_throughput = sum(self.throughputs) / len(self.throughputs)

        # If latency too high, reduce batch size
        if avg_latency > 100:  # 100ms SLA
            self.batch_size = max(1, self.batch_size - 4)

        # If latency acceptable and GPU underutilized, increase batch size
        elif avg_latency < 50:
            self.batch_size = min(128, self.batch_size + 4)

    async def process_batch(self, batch):
        start = time.time()

        # Process batch
        with torch.no_grad():
            results = self.model(batch)

        # Record metrics
        elapsed = time.time() - start
        self.latencies.append(elapsed * 1000)
        self.throughputs.append(len(batch) / elapsed)

        # Adjust for next batch
        self.adjust_batch_size()

        return results
```

### GPU Utilization

#### Mixed Precision Training

```python
from torch.cuda.amp import autocast, GradScaler

model = model.cuda()
optimizer = torch.optim.Adam(model.parameters())
scaler = GradScaler()

for epoch in range(num_epochs):
    for data, target in dataloader:
        data, target = data.cuda(), target.cuda()

        optimizer.zero_grad()

        # Automatic mixed precision
        with autocast():
            output = model(data)
            loss = criterion(output, target)

        # Scaled backprop
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

# Performance improvement:
# FP32:   100ms/batch, 8GB memory
# FP16:   40ms/batch,  4GB memory (2.5x faster, 2x less memory)
```

#### CUDA Streams for Overlapping

```python
import torch

# Create CUDA streams
stream1 = torch.cuda.Stream()
stream2 = torch.cuda.Stream()

# Process batches in parallel streams
with torch.cuda.stream(stream1):
    output1 = model(batch1)

with torch.cuda.stream(stream2):
    output2 = model(batch2)

# Wait for both to complete
torch.cuda.synchronize()

# Use both outputs
results = torch.cat([output1, output2])
```

#### TensorRT Optimization

```python
import torch
import torch_tensorrt

model = load_model().eval().cuda()

# Convert to TensorRT
trt_model = torch_tensorrt.compile(
    model,
    inputs=[
        torch_tensorrt.Input(
            min_shape=(1, 3, 224, 224),
            opt_shape=(8, 3, 224, 224),
            max_shape=(32, 3, 224, 224),
        )
    ],
    enabled_precisions={torch.float, torch.half},  # FP32 and FP16
    workspace_size=1 << 30  # 1GB
)

# Save optimized model
torch.jit.save(trt_model, "model_trt.ts")

# Inference
with torch.no_grad():
    output = trt_model(input_tensor)

# Performance:
# PyTorch:    50ms
# TensorRT:   15ms (3.3x faster)
```

---

## Docker Optimizations

### Image Size Reduction

#### Multi-Stage Builds

```dockerfile
# Bad: Single stage (2.5GB image)
FROM python:3.11
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app
WORKDIR /app
CMD ["python", "app.py"]

# Good: Multi-stage build (500MB image)
# Build stage
FROM python:3.11 as builder

WORKDIR /app
COPY requirements.txt .

# Install to user site
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Copy only installed packages
COPY --from=builder /root/.local /root/.local
COPY . /app

WORKDIR /app

# Ensure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

CMD ["python", "app.py"]

# Size comparison:
# Single stage:     2.5GB
# Multi-stage:      500MB (5x smaller)
# Build time:       Same (build cache helps)
```

#### Layer Optimization

```dockerfile
# Bad: Each RUN creates a layer
FROM python:3.11-slim
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y git
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*

# Good: Combine related commands
FROM python:3.11-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Even better: Multi-stage for build dependencies
FROM python:3.11-slim as base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Runtime dependencies only
        libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

FROM base as builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Build dependencies
        build-essential \
        git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM base

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . /app
WORKDIR /app

CMD ["python", "app.py"]
```

#### .dockerignore

```dockerfile
# .dockerignore - Reduce build context

# Git
.git
.gitignore
.gitattributes

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.pytest_cache
.coverage

# IDE
.vscode
.idea
*.swp
*.swo

# Documentation
*.md
docs/

# CI/CD
.github
.gitlab-ci.yml

# Data and models (use volumes instead)
data/
models/*.pth
*.h5

# Logs
*.log
logs/

# Environment
.env
.env.local
venv/
env/

# Tests
tests/
test_*.py

# Build artifacts
*.tar.gz
*.zip

# Result:
# Without .dockerignore: 2.5GB build context
# With .dockerignore:    50MB build context (50x smaller)
```

### Build Cache Optimization

#### Order Layers by Change Frequency

```dockerfile
# Bad: Code changes invalidate all layers
FROM python:3.11-slim

COPY . /app
RUN pip install -r /app/requirements.txt

WORKDIR /app
CMD ["python", "app.py"]

# Good: Dependencies cached separately
FROM python:3.11-slim

# Cached layer (changes rarely)
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Changes frequently
COPY . /app

WORKDIR /app
CMD ["python", "app.py"]

# Build time comparison (code change):
# Bad:  5 minutes (reinstalls all dependencies)
# Good: 10 seconds (uses cached dependencies)
```

#### BuildKit and Cache Mounts

```dockerfile
# syntax=docker/dockerfile:1.4

FROM python:3.11-slim

# Use BuildKit cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Persistent cache across builds
# First build:  200s
# Second build: 10s (cache hit)
```

**Build with BuildKit:**

```bash
# Enable BuildKit
export DOCKER_BUILDKIT=1

# Build with cache
docker build -t myapp:latest .

# Build with inline cache for CI
docker build \
  --cache-from myapp:latest \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  -t myapp:latest .
```

### Runtime Optimizations

#### Use Non-Root User

```dockerfile
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 appuser

# Install dependencies as root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=appuser:appuser . /app

# Switch to non-root user
USER appuser
WORKDIR /app

CMD ["python", "app.py"]

# Security: Prevents privilege escalation
# Performance: No impact
```

#### Optimize Python Startup

```dockerfile
FROM python:3.11-slim

# Set Python optimizations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pre-compile Python files
COPY . /app
WORKDIR /app
RUN python -m compileall .

CMD ["python", "-OO", "app.py"]

# Startup time:
# Default:     500ms
# Optimized:   200ms (2.5x faster)
```

---

## Kubernetes Optimizations

### Resource Management

#### Right-Sizing Resources

```yaml
# Bad: Overprovisioned
apiVersion: v1
kind: Pod
metadata:
  name: model-serving
spec:
  containers:
  - name: app
    image: model-serving:latest
    resources:
      requests:
        memory: "8Gi"    # App uses 2Gi
        cpu: "4"         # App uses 1 CPU
      limits:
        memory: "16Gi"
        cpu: "8"

# Good: Right-sized
apiVersion: v1
kind: Pod
metadata:
  name: model-serving
spec:
  containers:
  - name: app
    image: model-serving:latest
    resources:
      requests:
        memory: "2.5Gi"  # Actual usage + buffer
        cpu: "1"
      limits:
        memory: "4Gi"    # Allow some headroom
        cpu: "2"         # Allow burst

# Cost savings:
# Overprovisioned: $500/month
# Right-sized:     $150/month (3.3x cheaper)
```

**Find right size with monitoring:**

```bash
# Check actual usage
kubectl top pod model-serving

# Historical data with metrics-server
kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods | jq .

# Recommendations with VPA (Vertical Pod Autoscaler)
kubectl get vpa model-serving -o yaml

# Example output:
# recommendation:
#   containerRecommendations:
#   - containerName: app
#     lowerBound:
#       cpu: 500m
#       memory: 1.5Gi
#     target:
#       cpu: 1
#       memory: 2Gi
#     upperBound:
#       cpu: 2
#       memory: 4Gi
```

#### Quality of Service (QoS)

```yaml
# Guaranteed QoS (highest priority)
resources:
  requests:
    memory: "2Gi"
    cpu: "1"
  limits:
    memory: "2Gi"  # Same as request
    cpu: "1"       # Same as request

# Burstable QoS (medium priority)
resources:
  requests:
    memory: "2Gi"
    cpu: "1"
  limits:
    memory: "4Gi"  # Higher than request
    cpu: "2"       # Higher than request

# BestEffort QoS (lowest priority)
# No resources specified
```

### Autoscaling

#### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: model-serving-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-serving
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # Target 70% CPU
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80  # Target 80% memory
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
      policies:
      - type: Percent
        value: 50  # Scale down max 50% at a time
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0  # Scale up immediately
      policies:
      - type: Percent
        value: 100  # Can double replicas
        periodSeconds: 15
      - type: Pods
        value: 4  # Or add 4 pods
        periodSeconds: 15
      selectPolicy: Max  # Use whichever scales faster
```

**Custom Metrics HPA:**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: model-serving-hpa-custom
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-serving
  minReplicas: 2
  maxReplicas: 20
  metrics:
  # Scale based on request rate
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "100"  # 100 req/s per pod
  # Scale based on queue depth
  - type: External
    external:
      metric:
        name: sqs_queue_depth
      target:
        type: AverageValue
        averageValue: "30"  # 30 messages per pod
```

#### Cluster Autoscaler

```yaml
# Configure node pool for autoscaling
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-config
  namespace: kube-system
data:
  scale-down-delay-after-add: "10m"
  scale-down-unneeded-time: "10m"
  skip-nodes-with-local-storage: "false"
  skip-nodes-with-system-pods: "true"

---
# Node pool configuration (cloud-specific)
# GKE example:
# gcloud container node-pools create model-serving \
#   --cluster=my-cluster \
#   --enable-autoscaling \
#   --min-nodes=2 \
#   --max-nodes=10 \
#   --machine-type=n1-standard-4
```

### Pod Disruption Budgets

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: model-serving-pdb
spec:
  minAvailable: 2  # Always keep at least 2 pods running
  selector:
    matchLabels:
      app: model-serving

# Or use percentage:
# spec:
#   maxUnavailable: 25%  # Allow up to 25% pods down
```

### Network Performance

#### Service Mesh Optimization

```yaml
# Istio: Reduce sidecar resource usage
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-sidecar-injector
  namespace: istio-system
data:
  values: |
    sidecarInjectorWebhook:
      resources:
        requests:
          cpu: 10m     # Reduced from 100m
          memory: 40Mi  # Reduced from 128Mi
        limits:
          cpu: 100m
          memory: 128Mi
```

#### DNS Caching

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        kubernetes cluster.local in-addr.arpa ip6.arpa {
          pods insecure
          fallthrough in-addr.arpa ip6.arpa
        }
        cache 30  # Cache DNS for 30s
        loop
        reload
        loadbalance
    }
```

---

## Database Optimizations

### Query Optimization

#### Use Indexes

```sql
-- Bad: Full table scan
SELECT * FROM predictions
WHERE model_id = 'resnet50'
  AND created_at > '2025-10-01';

EXPLAIN ANALYZE;
-- Seq Scan on predictions (cost=0.00..15234.56 rows=1000)
-- Execution time: 234.567 ms

-- Good: Create indexes
CREATE INDEX idx_predictions_model_created
ON predictions(model_id, created_at);

-- Same query now uses index
EXPLAIN ANALYZE;
-- Index Scan using idx_predictions_model_created (cost=0.42..125.67 rows=1000)
-- Execution time: 2.345 ms (100x faster!)
```

#### Optimize WHERE Clauses

```sql
-- Bad: Function on indexed column
SELECT * FROM predictions
WHERE DATE(created_at) = '2025-10-16';

-- Good: Range query on indexed column
SELECT * FROM predictions
WHERE created_at >= '2025-10-16 00:00:00'
  AND created_at < '2025-10-17 00:00:00';

-- Bad: Leading wildcard
SELECT * FROM predictions
WHERE model_id LIKE '%net50';

-- Good: Trailing wildcard
SELECT * FROM predictions
WHERE model_id LIKE 'resnet50%';
```

#### Use EXPLAIN ANALYZE

```sql
-- Analyze query performance
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT p.id, p.result, m.name
FROM predictions p
JOIN models m ON p.model_id = m.id
WHERE p.created_at > NOW() - INTERVAL '1 day';

-- Look for:
-- 1. Seq Scan → Add index
-- 2. High cost → Optimize query
-- 3. Many buffer reads → Data not in cache
```

### Indexing Strategies

#### Composite Indexes

```sql
-- Query pattern:
-- SELECT * FROM predictions
-- WHERE model_id = ? AND status = ? AND created_at > ?

-- Bad: Separate indexes
CREATE INDEX idx_model ON predictions(model_id);
CREATE INDEX idx_status ON predictions(status);
CREATE INDEX idx_created ON predictions(created_at);
-- Each query uses only one index

-- Good: Composite index (most selective first)
CREATE INDEX idx_predictions_composite
ON predictions(model_id, status, created_at);
-- Single index covers entire query
```

#### Partial Indexes

```sql
-- Only 5% of predictions are pending
CREATE INDEX idx_pending_predictions
ON predictions(created_at)
WHERE status = 'pending';

-- Index size:
-- Full index:    500MB
-- Partial index: 25MB (20x smaller, much faster)
```

#### Include Columns (Covering Indexes)

```sql
-- Query:
-- SELECT id, result, created_at
-- FROM predictions
-- WHERE model_id = 'resnet50'

-- Good: Index includes needed columns
CREATE INDEX idx_predictions_covering
ON predictions(model_id)
INCLUDE (id, result, created_at);

-- Result: Index-only scan (no table access needed)
```

### Connection Pooling

```python
from sqlalchemy import create_engine, pool

# Bad: No pooling (new connection per request)
def get_connection():
    return create_engine('postgresql://...').connect()

# Good: Connection pooling
engine = create_engine(
    'postgresql://user:pass@localhost/mydb',
    poolclass=pool.QueuePool,
    pool_size=20,          # Persistent connections
    max_overflow=10,       # Extra connections under load
    pool_timeout=30,       # Wait time for connection
    pool_recycle=3600,     # Recycle after 1 hour
    pool_pre_ping=True,    # Test connection before use
    echo_pool=True,        # Log pool events
)

def get_prediction(pred_id):
    with engine.connect() as conn:
        result = conn.execute(
            'SELECT * FROM predictions WHERE id = %s',
            (pred_id,)
        )
        return result.fetchone()

# Performance:
# No pooling:        50ms per query (connection overhead)
# With pooling:      5ms per query (10x faster)
```

### Database Configuration

```sql
-- PostgreSQL optimizations

-- Shared buffers (25% of RAM)
ALTER SYSTEM SET shared_buffers = '8GB';

-- Effective cache size (50-75% of RAM)
ALTER SYSTEM SET effective_cache_size = '24GB';

-- Work memory (per operation)
ALTER SYSTEM SET work_mem = '64MB';

-- Maintenance work memory
ALTER SYSTEM SET maintenance_work_mem = '1GB';

-- Checkpoint settings (reduce I/O spikes)
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET max_wal_size = '4GB';

-- Random page cost (SSD)
ALTER SYSTEM SET random_page_cost = 1.1;  -- Default 4.0 for HDD

-- Parallel query
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;

-- Reload configuration
SELECT pg_reload_conf();
```

---

## Network Optimizations

### Compression

#### HTTP Compression

```python
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI()

# Add gzip compression
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # Only compress responses > 1KB
    compresslevel=6     # Balance between speed and compression
)

@app.get("/predictions")
async def get_predictions():
    # Returns large JSON response
    return {"predictions": [...]}  # 500KB

# Response sizes:
# Uncompressed: 500KB
# Compressed:   50KB (10x smaller)
# CPU cost:     ~5ms
```

#### Request/Response Compression

```python
import gzip
import json

# Compress large payloads
def compress_response(data):
    json_str = json.dumps(data)
    compressed = gzip.compress(json_str.encode('utf-8'))
    return compressed

# Client decompresses
def decompress_request(compressed_data):
    decompressed = gzip.decompress(compressed_data)
    return json.loads(decompressed.decode('utf-8'))
```

### HTTP/2 and gRPC

#### gRPC for Inter-Service Communication

```python
# gRPC service definition (model_service.proto)
# syntax = "proto3";
#
# service ModelService {
#   rpc Predict (PredictRequest) returns (PredictResponse) {}
# }
#
# message PredictRequest {
#   string model_id = 1;
#   repeated float input = 2;
# }
#
# message PredictResponse {
#   repeated float output = 1;
#   float inference_time_ms = 2;
# }

import grpc
from concurrent import futures
import model_service_pb2
import model_service_pb2_grpc

class ModelServicer(model_service_pb2_grpc.ModelServiceServicer):
    def Predict(self, request, context):
        # Process request
        output = model.predict(request.input)

        return model_service_pb2.PredictResponse(
            output=output,
            inference_time_ms=elapsed
        )

# Server
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
model_service_pb2_grpc.add_ModelServiceServicer_to_server(
    ModelServicer(), server
)
server.add_insecure_port('[::]:50051')
server.start()

# Client
channel = grpc.insecure_channel('localhost:50051')
stub = model_service_pb2_grpc.ModelServiceStub(channel)

response = stub.Predict(
    model_service_pb2.PredictRequest(
        model_id='resnet50',
        input=[1.0, 2.0, 3.0]
    )
)

# Performance comparison:
# REST/JSON:  10ms latency, 5KB payload
# gRPC:       3ms latency, 1KB payload (3.3x faster, 5x smaller)
```

### CDN and Caching

#### Cache-Control Headers

```python
from fastapi import FastAPI, Response

app = FastAPI()

@app.get("/models/{model_id}")
async def get_model_info(model_id: str, response: Response):
    # Model metadata changes rarely
    response.headers["Cache-Control"] = "public, max-age=3600"  # 1 hour
    response.headers["ETag"] = f'"{model_id}-v1"'

    return {"model_id": model_id, "version": "v1"}

@app.get("/predictions/{pred_id}")
async def get_prediction(pred_id: str, response: Response):
    # Predictions never change
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["ETag"] = f'"{pred_id}"'

    return {"id": pred_id, "result": [...]}
```

---

## Cost Optimization

### Resource Right-Sizing

#### Use VPA Recommendations

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: model-serving-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-serving
  updatePolicy:
    updateMode: "Off"  # Recommendation only
```

```bash
# Get recommendations
kubectl get vpa model-serving-vpa -o yaml

# Apply recommendations
kubectl get vpa model-serving-vpa -o jsonpath='{.status.recommendation.containerRecommendations[0].target}'
```

### Spot Instances

```yaml
# Node pool with spot instances (GKE example)
apiVersion: v1
kind: NodePool
metadata:
  name: spot-pool
spec:
  config:
    machineType: n1-standard-4
    preemptible: true  # Use spot instances
  autoscaling:
    enabled: true
    minNodeCount: 0
    maxNodeCount: 10

---
# Tolerations for spot instances
apiVersion: apps/v1
kind: Deployment
metadata:
  name: batch-processing
spec:
  template:
    spec:
      tolerations:
      - key: "cloud.google.com/gke-preemptible"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"
      nodeSelector:
        cloud.google.com/gke-preemptible: "true"

# Cost savings:
# On-demand:  $300/month
# Spot:       $90/month (70% discount)
```

### Reserved Capacity

**Cost comparison:**

| Instance Type | On-Demand | 1-Year Reserved | 3-Year Reserved | Savings |
|---------------|-----------|-----------------|-----------------|---------|
| m5.2xlarge    | $0.384/hr | $0.250/hr       | $0.192/hr       | 50%     |
| p3.2xlarge (GPU) | $3.06/hr | $1.99/hr     | $1.53/hr        | 50%     |

**Strategy:**
- Use reserved instances for baseline capacity
- Use on-demand/spot for burst capacity

---

## Monitoring and Profiling

### Application Profiling

```python
import cProfile
import pstats
import time
from functools import wraps

class Profiler:
    def __init__(self):
        self.profiler = cProfile.Profile()
        self.enabled = False

    def start(self):
        self.enabled = True
        self.profiler.enable()

    def stop(self):
        self.enabled = False
        self.profiler.disable()

    def stats(self, sort_by='cumulative', limit=20):
        stats = pstats.Stats(self.profiler)
        stats.strip_dirs()
        stats.sort_stats(sort_by)
        stats.print_stats(limit)

# Global profiler
profiler = Profiler()

# Profile endpoint
@app.post("/predict")
async def predict_endpoint(data: dict):
    profiler.start()
    try:
        result = await predict(data)
        return result
    finally:
        profiler.stop()

# View stats
@app.get("/debug/profile")
async def view_profile():
    profiler.stats()
    return {"message": "Check logs for profile"}
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Number of active HTTP requests'
)

# Instrumentation
@app.middleware("http")
async def prometheus_middleware(request, call_next):
    ACTIVE_REQUESTS.inc()
    start = time.time()

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        elapsed = time.time() - start
        ACTIVE_REQUESTS.dec()

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=status
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(elapsed)

    return response
```

---

## Project-Specific Optimizations

### Project 01: Model Serving API Optimizations

#### Optimization Checklist

```markdown
- [ ] Model loaded once at startup (not per request)
- [ ] Model compiled with torch.compile() (PyTorch 2.0+)
- [ ] Inference uses torch.no_grad()
- [ ] Input preprocessing cached
- [ ] Response uses FastAPI streaming for large outputs
- [ ] Gunicorn/Uvicorn with multiple workers
- [ ] Connection pooling for database
- [ ] Redis cache for frequent predictions
- [ ] Prometheus metrics enabled
- [ ] Docker image <500MB
```

#### Implementation

```python
# Optimized model serving
import torch
from fastapi import FastAPI
from functools import lru_cache

app = FastAPI()

# Load model once at startup
@lru_cache(maxsize=1)
def get_model():
    model = torch.load('/models/model.pth')
    model.eval()

    # Compile for faster inference (PyTorch 2.0+)
    model = torch.compile(model)

    return model

@app.post("/predict")
async def predict(data: dict):
    model = get_model()

    # Prepare input
    input_tensor = torch.tensor(data['input'])

    # Inference without gradients
    with torch.no_grad():
        output = model(input_tensor)

    return {"prediction": output.tolist()}

# Run with:
# uvicorn main:app --workers 4 --loop uvloop
```

**Performance Results:**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Latency (p50) | 150ms | 45ms | 3.3x faster |
| Latency (p95) | 500ms | 80ms | 6.2x faster |
| Throughput | 50 req/s | 200 req/s | 4x higher |
| Memory | 2GB | 800MB | 2.5x less |
| Docker image | 2.5GB | 450MB | 5.5x smaller |

### Project 02: Multi-Model Serving Optimizations

#### Model Registry with Lazy Loading

```python
from typing import Dict
import torch
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ModelMetadata:
    model_id: str
    path: str
    loaded_at: Optional[datetime] = None
    access_count: int = 0
    last_access: Optional[datetime] = None

class OptimizedModelRegistry:
    def __init__(self, max_loaded=3):
        self.registry: Dict[str, ModelMetadata] = {}
        self.loaded_models: Dict[str, torch.nn.Module] = {}
        self.max_loaded = max_loaded

    def register(self, model_id: str, path: str):
        self.registry[model_id] = ModelMetadata(
            model_id=model_id,
            path=path
        )

    def get_model(self, model_id: str):
        # Return if already loaded
        if model_id in self.loaded_models:
            self._update_access(model_id)
            return self.loaded_models[model_id]

        # Load model
        metadata = self.registry[model_id]
        model = torch.load(metadata.path)
        model.eval()
        model = torch.compile(model)

        # Evict least recently used if at capacity
        if len(self.loaded_models) >= self.max_loaded:
            self._evict_lru()

        # Cache model
        self.loaded_models[model_id] = model
        metadata.loaded_at = datetime.now()
        self._update_access(model_id)

        return model

    def _evict_lru(self):
        # Find least recently used
        lru_id = min(
            self.registry.keys(),
            key=lambda k: self.registry[k].last_access or datetime.min
        )

        # Remove from cache
        if lru_id in self.loaded_models:
            del self.loaded_models[lru_id]
            self.registry[lru_id].loaded_at = None

    def _update_access(self, model_id: str):
        metadata = self.registry[model_id]
        metadata.access_count += 1
        metadata.last_access = datetime.now()

# Usage
registry = OptimizedModelRegistry(max_loaded=3)
registry.register("resnet50", "/models/resnet50.pth")
registry.register("vgg16", "/models/vgg16.pth")
registry.register("efficientnet", "/models/efficientnet.pth")

# Only loads models when needed
model = registry.get_model("resnet50")
```

**Performance Results:**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Cold start | 2000ms | 200ms | 10x faster |
| Memory (3 models) | 6GB | 2GB | 3x less |
| Model switch | 500ms | 5ms | 100x faster |

### Project 03: GPU-Accelerated Inference Optimizations

#### Batching with GPU

```python
import torch
import asyncio
from collections import deque
from typing import List, Tuple

class GPUBatchProcessor:
    def __init__(
        self,
        model,
        max_batch_size=32,
        max_wait_time=0.01,
        device='cuda'
    ):
        self.model = model.to(device).eval()
        self.model = torch.compile(self.model)
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.device = device
        self.queue = asyncio.Queue()

        # Enable TF32 for better performance
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    async def predict(self, data: torch.Tensor):
        future = asyncio.Future()
        await self.queue.put((data, future))
        return await future

    async def process_batches(self):
        while True:
            batch = await self._collect_batch()
            if batch:
                await self._process_batch(batch)
            else:
                await asyncio.sleep(0.001)

    async def _collect_batch(self):
        batch = []
        deadline = asyncio.get_event_loop().time() + self.max_wait_time

        while len(batch) < self.max_batch_size:
            timeout = max(0, deadline - asyncio.get_event_loop().time())
            try:
                item = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=timeout
                )
                batch.append(item)
            except asyncio.TimeoutError:
                break

        return batch

    async def _process_batch(self, batch):
        data_list, futures = zip(*batch)

        # Stack and move to GPU
        batch_tensor = torch.stack(data_list).to(
            self.device,
            non_blocking=True
        )

        # Inference with mixed precision
        with torch.no_grad():
            with torch.cuda.amp.autocast():
                results = self.model(batch_tensor)

        # Move back to CPU
        results = results.cpu()

        # Return results
        for future, result in zip(futures, results):
            future.set_result(result)

# Usage
processor = GPUBatchProcessor(
    model,
    max_batch_size=32,
    max_wait_time=0.01
)

# Start processor
asyncio.create_task(processor.process_batches())

# Submit requests
results = await asyncio.gather(*[
    processor.predict(input_data)
    for input_data in requests
])
```

**Performance Results:**

| Metric | Before (sequential) | After (batched) | Improvement |
|--------|---------------------|-----------------|-------------|
| Throughput | 100 req/s | 800 req/s | 8x higher |
| GPU utilization | 30% | 85% | 2.8x better |
| Latency (p50) | 10ms | 15ms | 1.5x higher |
| Latency (p95) | 12ms | 25ms | 2x higher |
| Cost per 1M req | $50 | $6.25 | 8x cheaper |

**Trade-off:** Higher throughput at cost of slightly higher latency

---

## Benchmarking Methodologies

### Load Testing

```python
import asyncio
import aiohttp
import time
from statistics import mean, median, stdev
import numpy as np

async def benchmark_endpoint(
    url: str,
    num_requests: int = 1000,
    concurrency: int = 10
):
    """Benchmark an HTTP endpoint"""

    latencies = []

    async def single_request(session, request_id):
        start = time.time()
        try:
            async with session.post(
                url,
                json={"input": [[1, 2, 3, 4]]}
            ) as response:
                await response.json()
                elapsed = time.time() - start
                latencies.append(elapsed * 1000)  # Convert to ms
                return True
        except Exception as e:
            print(f"Request {request_id} failed: {e}")
            return False

    # Run requests with concurrency limit
    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def limited_request(request_id):
            async with semaphore:
                return await single_request(session, request_id)

        start = time.time()
        results = await asyncio.gather(*[
            limited_request(i)
            for i in range(num_requests)
        ])
        total_time = time.time() - start

    # Calculate statistics
    successful = sum(results)
    latencies = sorted(latencies)

    print(f"\n{'='*60}")
    print(f"Benchmark Results")
    print(f"{'='*60}")
    print(f"Total requests:    {num_requests}")
    print(f"Successful:        {successful}")
    print(f"Failed:            {num_requests - successful}")
    print(f"Total time:        {total_time:.2f}s")
    print(f"Requests/sec:      {num_requests / total_time:.2f}")
    print(f"\nLatency (ms):")
    print(f"  Mean:            {mean(latencies):.2f}")
    print(f"  Median (p50):    {median(latencies):.2f}")
    print(f"  p95:             {np.percentile(latencies, 95):.2f}")
    print(f"  p99:             {np.percentile(latencies, 99):.2f}")
    print(f"  Min:             {min(latencies):.2f}")
    print(f"  Max:             {max(latencies):.2f}")
    print(f"  Std dev:         {stdev(latencies):.2f}")
    print(f"{'='*60}\n")

# Run benchmark
asyncio.run(benchmark_endpoint(
    "http://localhost:8080/predict",
    num_requests=1000,
    concurrency=10
))
```

### GPU Benchmarking

```python
import torch
import time
import numpy as np

def benchmark_gpu_model(
    model,
    input_shape,
    batch_sizes=[1, 8, 16, 32, 64],
    num_iterations=100,
    warmup=10
):
    """Benchmark model with different batch sizes"""

    model = model.cuda().eval()
    results = []

    for batch_size in batch_sizes:
        print(f"\nBenchmarking batch_size={batch_size}")

        # Create dummy input
        dummy_input = torch.randn(
            batch_size, *input_shape
        ).cuda()

        # Warmup
        with torch.no_grad():
            for _ in range(warmup):
                _ = model(dummy_input)

        # Benchmark
        torch.cuda.synchronize()
        start = time.time()

        with torch.no_grad():
            for _ in range(num_iterations):
                output = model(dummy_input)

        torch.cuda.synchronize()
        elapsed = time.time() - start

        # Calculate metrics
        avg_time = elapsed / num_iterations
        throughput = batch_size / avg_time
        latency = avg_time * 1000  # ms

        # GPU memory
        memory_allocated = torch.cuda.memory_allocated() / 1024**3
        memory_reserved = torch.cuda.memory_reserved() / 1024**3

        results.append({
            'batch_size': batch_size,
            'latency_ms': latency,
            'throughput': throughput,
            'memory_gb': memory_allocated
        })

        print(f"  Latency:     {latency:.2f}ms")
        print(f"  Throughput:  {throughput:.2f} samples/sec")
        print(f"  Memory:      {memory_allocated:.2f}GB")

    # Print summary table
    print(f"\n{'='*80}")
    print(f"{'Batch Size':<15} {'Latency (ms)':<15} {'Throughput':<20} {'Memory (GB)':<15}")
    print(f"{'='*80}")
    for r in results:
        print(f"{r['batch_size']:<15} {r['latency_ms']:<15.2f} "
              f"{r['throughput']:<20.2f} {r['memory_gb']:<15.2f}")
    print(f"{'='*80}\n")

    return results

# Run benchmark
results = benchmark_gpu_model(
    model,
    input_shape=(3, 224, 224),
    batch_sizes=[1, 8, 16, 32, 64]
)
```

---

## Real-World Optimization Case Studies

### Case Study 1: Reducing Inference Latency from 500ms to 50ms

**Problem:**
Production model serving API had p95 latency of 500ms, exceeding SLA of 200ms.

**Investigation:**

```bash
# Profiled inference endpoint
python -m cProfile -o profile.stats app.py

# Found bottlenecks:
# 1. Model loading on each request (300ms)
# 2. Preprocessing inefficient (100ms)
# 3. No torch.no_grad() (50ms)
# 4. Running on CPU (50ms)
```

**Optimizations Applied:**

1. **Load model once at startup**
   ```python
   # Before: Load per request
   def predict(data):
       model = torch.load('model.pth')
       return model(data)

   # After: Load once
   MODEL = torch.load('model.pth').eval()

   def predict(data):
       return MODEL(data)
   ```
   **Savings: 300ms → 0ms**

2. **Optimize preprocessing**
   ```python
   # Before: Loop
   def preprocess(data):
       result = []
       for item in data:
           result.append(transform(item))
       return result

   # After: Vectorized
   def preprocess(data):
       return torch.stack([transform(item) for item in data])
   ```
   **Savings: 100ms → 20ms**

3. **Disable gradients**
   ```python
   # Before:
   output = model(input)

   # After:
   with torch.no_grad():
       output = model(input)
   ```
   **Savings: 50ms → 0ms**

4. **Use GPU**
   ```python
   # Before: CPU
   model = model.cpu()

   # After: GPU
   model = model.cuda()
   ```
   **Savings: 50ms → 10ms**

**Results:**
- **Latency (p95):** 500ms → 50ms (10x faster)
- **Throughput:** 20 req/s → 200 req/s (10x higher)
- **Cost:** $500/mo → $100/mo (5x cheaper)

### Case Study 2: Scaling to 10x Traffic with Same Cost

**Problem:**
Traffic growing 10x, but budget couldn't increase.

**Solution Strategy:**

1. **Right-size resources**
   - Analyzed actual usage with VPA
   - Reduced requests from 4 CPU to 1 CPU
   - **Savings: 75% compute cost**

2. **Implement autoscaling**
   - Added HPA based on CPU and request rate
   - Min replicas: 2, Max replicas: 20
   - **Result: Auto-scale with traffic**

3. **Add caching**
   - Implemented Redis cache with TTL
   - Cache hit rate: 60%
   - **Savings: 60% fewer model inferences**

4. **Optimize Docker images**
   - Multi-stage builds
   - Image size: 2.5GB → 400MB
   - **Result: Faster deployments, lower storage**

5. **Use spot instances**
   - Moved batch processing to spot instances
   - **Savings: 70% on batch compute**

**Results:**
- **Handled 10x traffic** (100 → 1000 req/s)
- **Same cost** ($1000/mo)
- **Better latency** (100ms → 80ms p95)
- **Higher availability** (99.5% → 99.9%)

---

## Optimization Checklists

### Pre-Optimization Checklist

```markdown
- [ ] Established baseline metrics (latency, throughput, cost)
- [ ] Profiled application to find bottlenecks
- [ ] Identified optimization goals and priorities
- [ ] Set up monitoring and alerting
- [ ] Documented current architecture
- [ ] Created benchmark suite
```

### Code Optimization Checklist

```markdown
- [ ] Use appropriate data structures (list, dict, set)
- [ ] Avoid premature optimization
- [ ] Profile before optimizing
- [ ] Use built-in functions and libraries
- [ ] Minimize I/O operations
- [ ] Use generators for large datasets
- [ ] Cache expensive computations
- [ ] Vectorize with NumPy where possible
- [ ] Use async for I/O-bound operations
- [ ] Use multiprocessing for CPU-bound operations
```

### ML Model Optimization Checklist

```markdown
- [ ] Model loaded once at startup
- [ ] Inference uses torch.no_grad()
- [ ] Model in eval mode
- [ ] Batch processing implemented
- [ ] Mixed precision (FP16) enabled
- [ ] Model quantization considered
- [ ] Model pruning evaluated
- [ ] TensorRT/ONNX conversion explored
- [ ] GPU utilized if available
- [ ] Appropriate batch size chosen
```

### Infrastructure Optimization Checklist

```markdown
- [ ] Docker images optimized (<1GB)
- [ ] Multi-stage builds used
- [ ] .dockerignore configured
- [ ] Resource requests/limits set appropriately
- [ ] Autoscaling configured (HPA)
- [ ] Pod disruption budgets defined
- [ ] Connection pooling implemented
- [ ] Caching strategy in place
- [ ] Compression enabled
- [ ] Monitoring and metrics configured
```

---

## Resources and References

### Official Documentation

- **PyTorch Performance**: https://pytorch.org/tutorials/recipes/recipes/tuning_guide.html
- **FastAPI Performance**: https://fastapi.tiangolo.com/deployment/concepts/
- **Kubernetes Best Practices**: https://kubernetes.io/docs/concepts/configuration/overview/
- **PostgreSQL Performance**: https://www.postgresql.org/docs/current/performance-tips.html

### Tools

- **Profiling**: cProfile, py-spy, line_profiler, memory_profiler
- **Benchmarking**: locust, k6, hey, wrk
- **Monitoring**: Prometheus, Grafana, Datadog, New Relic
- **Database**: pgBadger, EXPLAIN ANALYZE, pg_stat_statements

### Books

- "High Performance Python" by Micha Gorelick and Ian Ozsvald
- "Database Internals" by Alex Petrov
- "Designing Data-Intensive Applications" by Martin Kleppmann

---

**Remember:** Optimization is an iterative process. Always measure, optimize, and verify. Focus on the biggest bottlenecks first!
