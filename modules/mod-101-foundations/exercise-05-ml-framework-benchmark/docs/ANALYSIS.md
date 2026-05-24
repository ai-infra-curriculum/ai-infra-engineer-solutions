# Analysis Guide - mlbench

Reference companion to RESULTS.md. Explains how to interpret the benchmark output and decide whether to switch frameworks, tune a hyperparameter, or do nothing.

Most framework choices in real projects are made for the wrong reason (team familiarity, hype, a benchmark that doesn't match the workload). This file is here to slow that decision down.

## 1. The four questions every benchmark should answer

Before staring at a table of numbers:

1. Am I compute-bound or memory-bandwidth bound?
2. Is my batch size big enough to saturate the GPU?
3. Is compilation paying for itself?
4. What is the data path doing while the GPU is "fast"?

If you cannot answer these for your specific run, the benchmark numbers are anecdotes.

## 2. Compute-bound vs memory-bandwidth-bound

A workload is compute-bound when the GPU's tensor or CUDA cores are the bottleneck; it is memory-bandwidth-bound when moving weights and activations from HBM to the SMs is the bottleneck. Most "framework wins" come from one of:

- Better kernel selection (cuDNN heuristic chose well).
- Better memory layout (channels_last for convolutions on A100/H100).
- Fewer kernel launches (fusion).

### How to tell which regime you are in

| Signal | Likely regime |
|---|---|
| GPU utilization > 90%, throughput scales linearly with batch | Compute-bound: go fp16/bf16, or pick a smaller model |
| GPU utilization > 90%, throughput plateaus past a batch size | Compute-bound, hitting tensor-core ceiling |
| GPU utilization 50-80%, memory bandwidth near limit | Bandwidth-bound: quantize weights, fuse ops, prefer fp16/bf16 |
| GPU utilization < 50% | Data loading or host overhead, not the framework |
| Throughput sub-linear with batch growth, memory mostly flat | Kernel launch overhead: turn compilation on |

Tool: `nvidia-smi dmon -s pucvmet` gives `pwr,gpu,sm,mem,enc,dec,bw,fb,t` in one stream. Sit on it during a run.

### What this means for choosing a framework

- Compute-bound workloads (large CNNs, transformers at high batch): all three frameworks land within 10% when compiled. The underlying kernel is the same cuDNN / cuBLAS / cuTLASS. Pick by ergonomics.
- Memory-bandwidth-bound workloads (decoder inference, small batch sizes): differences open up. JAX's XLA tends to fuse more aggressively, reducing HBM round trips. The JAX wins in RESULTS.md section 2 come from this.
- Launch-overhead-bound workloads (lots of small kernels, RL training loops): compiled JAX or `torch.compile` make a 2-5x difference. Eager TensorFlow tends to lose here.

## 3. The role of compilation

`torch.compile`, `tf.function(jit_compile=True)`, and `jax.jit` all serve the same goal: turn a sequence of Python ops into one fused, ahead-of-time-optimized kernel graph.

### When compilation wins

- Stable input shapes. Recompilation triggers on shape changes; varying batch sizes thrash.
- Small ops dominated by launch overhead.
- Long-running jobs where the 10-40 s compilation cost is amortized.

### When compilation loses

- Short runs (training only a few epochs). Compile cost dominates wall time.
- Dynamic control flow inside the model. The compiler falls back to eager for unsupported ops, fragmenting the graph.
- Debugging. Compiled graphs hide intermediate tensors and make stack traces useless.

### Practical rule

Use compilation for training runs longer than 10 minutes and for production inference. Skip it for research iteration and runs under 5 minutes.

For `torch.compile`, prefer modes in this order:

1. `mode="reduce-overhead"` - best default, fixes most launch-overhead issues.
2. `mode="max-autotune"` - best for inference; spends more time finding kernels.
3. `mode="default"` - start here only if the other two break.

For `jax.jit`, donate buffers when you don't need the input afterwards:

```python
@partial(jax.jit, donate_argnums=(0,))
def step(state, batch):
    ...
```

This frees the previous state's memory, allowing JAX to reuse the allocation. Often 10-15% memory savings.

## 4. Batch size sensitivity

Throughput vs batch size is the most useful chart in a benchmark.

### Three regimes

```
throughput
  ^
  |     ......._______
  |    /
  |   /  <- linear scaling (we want this)
  |  /
  | /   <- ramp (kernel launch overhead dominates)
  |/_______
  +----------------> batch size
    small      sweet spot       wasted memory
```

- Small batch: GPU is starving. More samples per batch turns into more throughput almost 1:1.
- Sweet spot: throughput plateaus. Tensor cores are saturated.
- Above sweet spot: throughput is flat (or drops slightly due to L2 thrash) while memory grows linearly.

The right batch size is the smallest one in the plateau. Bigger wastes memory you could spend on a longer sequence or a bigger model.

### Cross-framework batch sensitivity

In our reference numbers, the sweet spot for ResNet-50 on A100 is:

- PyTorch: batch 256 (fp16, channels_last)
- TensorFlow: batch 256
- JAX: batch 128 (saturates earlier because fewer kernel launches => less wasted overhead at small batches)

If your benchmark shows a framework winning at batch 32 and losing at batch 256, you're probably comparing launch overhead, not real performance. Always sweep batch size.

## 5. FLOPs vs memory bandwidth - the roofline argument

The roofline model gives you a rough ceiling for any workload:

```
attainable_throughput = min(peak_flops, arithmetic_intensity * peak_bandwidth)
```

Where `arithmetic_intensity` = FLOPs per byte of memory accessed.

### Numbers for an A100 40GB SXM4

- Peak fp16 with tensor cores: ~312 TFLOPS
- Peak HBM2 bandwidth: ~1555 GB/s
- "Ridge point" (where the two bounds cross): arithmetic intensity ~200 FLOPs/byte

### Reading workloads

| Workload | Approx arithmetic intensity | Bound by |
|---|---|---|
| ResNet-50 training, batch 256 | ~600 FLOPs/byte | Compute |
| ViT-B/16 training, batch 256 | ~400 FLOPs/byte | Compute |
| GPT-2 inference, batch 1 | ~5 FLOPs/byte | Bandwidth |
| LLM decoder, batch 1 | ~2 FLOPs/byte | Bandwidth |
| MLP, large batch | ~50 FLOPs/byte | Bandwidth |
| Sparse attention | ~10 FLOPs/byte | Bandwidth |

### Implications for the framework choice

- Compute-bound: framework matters less. Squeeze the last 10% via mixed precision and compilation.
- Bandwidth-bound: every byte counts. Use 8-bit / 4-bit quantization; fuse aggressively (JAX's structural advantage); avoid unnecessary precision (bf16 over fp32 for weights).

## 6. When to switch frameworks

A framework change costs weeks of engineering. Don't do it for a benchmark win under 30%. Realistic triggers:

| Reason | Switch from | Switch to |
|---|---|---|
| Need TPU support | PyTorch | JAX (or PyTorch/XLA, but JAX is more mature on TPU) |
| Need maximum production tooling, model zoo | JAX/TensorFlow | PyTorch |
| Need fastest static-graph training and TPU optionality | PyTorch | JAX |
| Need mobile/edge deployment | PyTorch/JAX | TensorFlow (TFLite) or ONNX export from PyTorch |
| Need largest inference ecosystem (vLLM, TGI, HuggingFace) | TF/JAX | PyTorch |
| Need fastest tabular | Any deep framework | XGBoost or LightGBM |
| Need lowest latency single-stream inference | Native framework | Export to ONNX Runtime or TensorRT |

The XGBoost row matters more than people expect. If your data has under 10M rows and under 1000 features, gradient-boosted trees usually beat deep models on both speed and accuracy. Benchmarking PyTorch vs TensorFlow on that data is the wrong axis.

## 7. "Why did framework X win?" - pattern playbook

When you see a win, the explanation is usually one of these. Eliminate from the top:

1. Different precision. One run was bf16, the other fp32. Check `precision` in the JSON.
2. One was compiled, the other was not. Check `compiled` and `compile_method`.
3. Different batch size. Check `batch_size`.
4. Different effective batch (gradient accumulation). Frameworks differ in how they implement accumulation efficiently.
5. Different kernel selection. cuDNN's heuristic can pick suboptimally; rerun with cuDNN benchmark mode on.
6. Different memory layout. PyTorch defaults to `channels_first`; on A100 with conv layers, `channels_last` is 10-20% faster.
7. Different number of dataloader workers. PyTorch defaults to 0; this can starve the GPU. TF and JAX use the host runtime differently.
8. Different padding / attention mask handling. A transformer benchmark where one framework drops a token-cost and another does not will skew throughput.
9. Different `synchronize()` behavior. If your timing harness does not `cuda.synchronize()` between iterations, you may be timing kernel launches, not kernel execution. Asynchronous = "free" until you wait.
10. Different test architecture. The "Transformer" model isn't standard. Confirm both frameworks built the same parameter count and FLOPs.

If you eliminate all ten and there's still a 20%+ gap, you have a real finding. Write it down with the run IDs and post it.

## 8. How to read the produced charts

For each chart in `mlbench report`, here's what good looks like and what bad looks like.

### Throughput vs batch size

- Good: monotonic increase up to a plateau.
- Bad: bumpy curve - cudnn benchmark mode is off or there is host-side noise.
- Worse: throughput collapses at large batch - OOM driven, or you crossed the L2 cache line and got NUMA penalties.

### Latency CDF

- Good: P99 close to P50 (factor of ~2). Tight tail.
- Bad: P99 is 5-10x P50. You have a slow path (cold cache, GC, allocator) firing periodically.

### GPU utilization timeline

- Good: flat near 85-95%.
- Bad: sawtooth pattern - data loader is the bottleneck. Increase `num_workers`, enable `prefetch`, or move preprocessing to GPU.

### Peak memory vs throughput scatter

- The Pareto frontier (top-left points: low memory, high throughput) is your shopping list.
- Frameworks dominated everywhere by another are candidates for elimination.

### Compilation overhead waterfall

- The first 5-50 iterations are the compile cost. If your job runs for fewer than 1000 iterations total, compilation may net out negative.
- For repeat workloads, cache the compiled graph to disk (PyTorch persistent inductor cache via `torch._dynamo.config.cache_size_limit`; JAX persistent cache via `jax.config.update("jax_compilation_cache_dir", path)`) so you only pay it once across runs.

## 9. Quick decision flow

```
Q: Is my workload tabular with under 10M rows?
   -> Yes -> XGBoost / LightGBM. Do not benchmark deep frameworks.
   -> No

Q: Am I planning to deploy to TPUs?
   -> Yes -> JAX (or PyTorch/XLA).
   -> No

Q: Am I planning to deploy to mobile/edge?
   -> Yes -> TensorFlow Lite or ONNX export from PyTorch.
   -> No

Q: Will my workload run for more than 10 minutes per session?
   -> Yes -> Enable compilation.
   -> No

Q: Do I need fast research iteration with great debugger UX?
   -> Yes -> PyTorch eager.
   -> No

Q: Is the workload heavily attention-based (transformers) with stable shapes?
   -> Yes -> JAX has a structural edge.
   -> No  -> PyTorch is the default. Ecosystem will save you more time than framework speed.
```

## 10. Final cautions

- One benchmark, one workload. Numbers in this exercise are for synthetic ImageNet-shaped data and a fixed model zoo. Your data will differ in I/O cost, augmentation cost, and model architecture.
- Hardware generation matters more than framework. Moving from V100 to A100 changes the right answer to "what's fast?" more than swapping PyTorch for JAX. Re-benchmark when you change hardware.
- The fastest framework isn't always cheapest. Per-hour cost of an A100 vs an A10 differs more than a 30% throughput gap. Cost per training run / cost per million inferences is the metric that pays the bills.
- Numbers age fast. PyTorch 2.4 was 2x faster than 2.2 on some workloads. Re-run benchmarks at least once per framework major version.

See RESULTS.md for the raw numbers backing this analysis.