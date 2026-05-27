# SOLUTION — GPU Computing

> Read this *after* you have benchmarked the reference GPU code on
> a real device. This document explains *why* the kernels and
> infrastructure choices are shaped the way they are and how to
> read GPU performance signals correctly.

## What this module is really teaching

The performance track (mod-001 → mod-008) gives you the mental
model for GPU performance. This module is the **engineer-facing
implementation** of that model:

- Introspection tooling that surfaces the right metrics.
- CUDA kernels written defensively for production.
- Memory profiling that finds OOMs before they happen.
- Multi-GPU training patterns that scale linearly.

## Architectural decisions and *why*

### Decision 1: ``pynvml``-based introspection, not parsing nvidia-smi

Exercise 01 (GPU introspection) uses the NVML Python bindings
directly. The reason: ``nvidia-smi`` output format changes
between driver versions; parsing it is fragile. ``pynvml`` is a
stable API.

The cost: pynvml requires NVIDIA's user-space libraries
installed. The benefit: introspection that doesn't break on
driver upgrades.

### Decision 2: One CUDA kernel implementation, multiple launches

Exercise 02 (CUDA kernel) provides one kernel with three launch
configurations (naive, tiled, vectorized). The reason: showing
the *progression* — same algorithm, 2-3x speedup at each step —
teaches the lesson that matters. A single "best" kernel hides
the engineering moves.

### Decision 3: Memory profiling at the PyTorch level

Exercise 07 (GPU memory profiling) uses
``torch.cuda.memory._record_memory_history()`` rather than
``cuda-memcheck`` or ``compute-sanitizer``. The reason: 95% of
real-world OOMs are caused by accidentally retained tensors in
Python code, not by CUDA bugs. PyTorch's profiler answers the
question engineers actually have ("why is my model OOMing at
step 4231").

### Decision 4: ``torch.distributed`` over Horovod for multi-GPU

The reference multi-GPU code uses ``torch.distributed`` directly.
The reason: Horovod was the right answer in 2019; in 2026,
PyTorch's native distributed support has caught up, has better
documentation, and is supported by the upstream team.

DDP (DistributedDataParallel) > DataParallel for almost
everything; the reference defaults to DDP and explicitly calls
out why DataParallel is no longer recommended.

### Decision 5: cuDNN benchmark on, deterministic off (by default)

For training, ``torch.backends.cudnn.benchmark = True`` is set
and ``torch.backends.cudnn.deterministic = False``. The reason:
deterministic mode costs 20-40% throughput; in 95% of training
scenarios you'd rather have the speedup than bit-exact
reproducibility. The reference flag for switching to
deterministic mode is documented for the cases where you need it
(regulated industries, debugging).

### Decision 6: Profiling artifacts saved as chrome-tracing JSON

Exercise 05/06 (profiler walkthroughs) save profiles in Chrome's
tracing JSON format. The reason: it opens in
``chrome://tracing`` or Perfetto without specialized tooling.
NSight is more powerful, but requires NVIDIA tooling installed
on the analyst's machine.

## Trade-offs we deliberately accepted

### NVIDIA-first

All exercises assume NVIDIA GPUs + CUDA. AMD (ROCm) and Intel
(oneAPI) have legitimate ML stacks but are still under-tooled
relative to NVIDIA. The patterns transfer; the specific tooling
doesn't.

### CPython interpreter, no Cython / pybind11 / Triton inside the kernel exercise

Exercise 02 stays in CUDA + Python. Triton is the modern path
for ML kernels and is covered in the performance track
(performance/mod-004). Bringing it into mod-107 would dilute the
"this is what CUDA actually looks like" learning goal.

### Memory profiling assumes PyTorch 2.x

The profiling APIs changed in PyTorch 2.x. The reference uses
the 2.x APIs because that's where everything is going; teams
still on 1.13 will need to port.

## Common mistakes graders see

1. **DataLoader with too few workers**: the GPU is starved
   waiting for data. Always size ``num_workers`` to at least
   2-4x the number of CPU cores per GPU.
2. **Mixing ``.to(device)`` and ``.cuda()`` in the same code**:
   inconsistent device handling causes subtle bugs.
3. **Forgetting to switch the module into inference mode**:
   BatchNorm keeps using the running statistics; dropout fires
   incorrectly. PyTorch exposes ``.train()`` / ``.eval()`` for
   exactly this purpose.
4. **Computing on CPU, moving to GPU only for the matmul**: the
   data-transfer time often dominates. Push tensors to GPU
   early.
5. **Ignoring ``cudaMemcpyAsync``**: synchronous copies block
   the GPU stream. Use the async variant + explicit streams.
6. **Profiling cold cache and panicking**: the first iteration
   pays JIT / lazy-loading costs. Always profile after
   warmup.

## When to go beyond this implementation

- Add **NVIDIA Nsight Systems** automation in CI to catch
  performance regressions.
- Move to **Triton** for kernels you'd otherwise write in CUDA;
  the productivity boost is 5-10x.
- Adopt **NCCL diagnostic tests** (mod-008 ex-03) for multi-node
  training verification.

## Related curriculum touchpoints

- ``performance/mod-001-gpu-fundamentals`` — the GPU
  metrics-first mental model.
- ``performance/mod-003-performance-profiling`` — deeper
  profiling workflows.
- ``performance/mod-008-advanced-topics`` — CUDA Graphs, FP8,
  MIG, and other advanced topics.
- ``engineer/mod-110-llm-infrastructure`` — applying GPU
  knowledge to LLM serving.
