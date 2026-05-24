# Benchmark Results — `mlbench`

This document defines the **result file schema** produced by `mlbench run`, presents **reference numbers** from a canonical hardware setup, and notes **reproducibility caveats** so you can compare your own runs apples-to-apples.

Numbers below were captured on **NVIDIA A100 40GB SXM4, CUDA 12.4, cuDNN 9.0**, with PyTorch 2.3.1, TensorFlow 2.15.0, JAX 0.4.26, XGBoost 2.0.3, on a 24-core EPYC 7443P host with 256 GB RAM. CPU-only rows used 16 threads pinned with `taskset`.

---

## 1. Result schema

`mlbench` writes a single JSON file per run. The shape is stable across versions; new fields are added but never removed.

```json
{
  "run_id": "20260524-A100-resnet50-v0.3.1",
  "version": "0.3.1",
  "created_at": "2026-05-24T13:42:08Z",
  "config": {
    "frameworks": ["pytorch", "tensorflow", "jax", "xgboost"],
    "models": ["resnet50", "vit-b16", "transformer-base", "mlp", "xgb-tabular"],
    "devices": ["cuda:0", "cpu"],
    "batch_sizes": [32, 64, 128, 256],
    "precision": ["fp32", "fp16", "bf16"],
    "num_epochs": 3,
    "warmup_iters": 50,
    "measure_iters": 200,
    "dataset": "synthetic",
    "seed": 42
  },
  "hardware": {
    "gpu": "NVIDIA A100-SXM4-40GB",
    "gpu_count": 1,
    "cuda": "12.4",
    "cudnn": "9.0.0",
    "driver": "550.54.14",
    "cpu": "AMD EPYC 7443P 24-Core",
    "ram_gb": 256
  },
  "results": [
    {
      "framework": "pytorch",
      "framework_version": "2.3.1+cu121",
      "model": "resnet50",
      "device": "cuda:0",
      "precision": "fp16",
      "batch_size": 256,
      "compiled": true,
      "compile_method": "torch.compile",
      "training_time_s": 38.42,
      "throughput_samples_per_sec": 1664.5,
      "inference_latency_ms_p50": 2.31,
      "inference_latency_ms_p95": 2.74,
      "inference_latency_ms_p99": 3.41,
      "peak_gpu_memory_mb": 14238,
      "peak_cpu_memory_mb": 5012,
      "gpu_utilization_avg": 0.89,
      "flops_estimated": 8.2e12,
      "energy_joules": 1452.3,
      "errors": []
    }
  ],
  "summary": {
    "fastest_training_overall": { "framework": "jax", "value_seconds": 35.1 },
    "fastest_inference_overall": { "framework": "pytorch", "value_ms": 2.31 },
    "most_memory_efficient": { "framework": "jax", "value_mb": 11804 },
    "highest_throughput": { "framework": "jax", "value_sps": 1810.2 }
  }
}
```

### Field definitions

| Field | Type | Meaning |
|---|---|---|
| `run_id` | string | Stable identifier — also the report folder name. |
| `version` | string | mlbench schema version. |
| `created_at` | ISO8601 | Wall-clock start of run. |
| `config` | object | The full input config; lets you reproduce. |
| `hardware` | object | Probed at startup via `nvidia-smi`, `lscpu`. |
| `results[]` | array | One entry per (framework, model, device, precision, batch_size) cell. |
| `results[].compiled` | bool | Whether graph compilation was used. `torch.compile` / `tf.function(jit_compile=True)` / `jax.jit`. |
| `results[].compile_method` | enum | `eager`, `torch.compile`, `xla`, `jax.jit`. |
| `results[].training_time_s` | float | Wall time for the configured number of epochs after warmup. |
| `results[].throughput_samples_per_sec` | float | Steady-state. Higher is better. |
| `results[].inference_latency_ms_p50/p95/p99` | float | Per single example (batch_size=1) inference latency. |
| `results[].peak_gpu_memory_mb` | int | From `torch.cuda.max_memory_allocated` / equivalent. |
| `results[].gpu_utilization_avg` | float | Mean SM utilization during measurement window. 0-1. |
| `results[].flops_estimated` | float | Forward FLOPs × samples processed. Useful for normalizing. |
| `results[].energy_joules` | float | From nvidia-smi power draw integral. GPU only; null on CPU rows. |
| `results[].errors` | array<string> | Empty on success. Populated with the error class if OOM/etc. |

### Reading the file

```bash
# What's fastest at fp16 batch 256?
jq '.results[]
    | select(.precision=="fp16" and .batch_size==256)
    | {framework, model, throughput_samples_per_sec}
    | .throughput_samples_per_sec' \
  results/20260524-A100-resnet50-v0.3.1.json
```

```python
# Or in Python
import json, pandas as pd
data = json.load(open("results/run.json"))
df = pd.DataFrame(data["results"])
print(df.groupby(["framework", "model"]).throughput_samples_per_sec.max())
```

---

## 2. Reference results — A100 40GB

### 2.1 ResNet-50 / ImageNet-like, training throughput (samples/sec, higher is better)

| Framework  | Precision | Batch | Eager | Compiled | Notes |
|---|---|---|---|---|---|
| PyTorch    | fp32 | 128 | 712  | 884  | `torch.compile(mode="reduce-overhead")` |
| PyTorch    | fp16 | 256 | 1340 | 1664 | autocast + channels_last |
| PyTorch    | bf16 | 256 | 1289 | 1601 | |
| TensorFlow | fp32 | 128 | 681  | 802  | `tf.function(jit_compile=True)` |
| TensorFlow | fp16 | 256 | 1244 | 1530 | mixed_precision policy |
| TensorFlow | bf16 | 256 | 1208 | 1492 | |
| JAX/Flax   | fp32 | 128 | 745  | 928  | `jax.jit`, donated buffers |
| JAX/Flax   | fp16 | 256 | 1402 | 1810 | bf16 preferred on A100 |
| JAX/Flax   | bf16 | 256 | 1438 | 1842 | **winner** |

**Takeaway**: JAX with `jit` + bf16 leads on A100 for static-graph CV. PyTorch closes most of the gap with `torch.compile`, at the cost of compilation time (10-40s up-front).

### 2.2 ResNet-50, inference latency (ms, batch=1, lower is better)

| Framework  | Precision | Eager P50 | Compiled P50 | Compiled P95 |
|---|---|---|---|---|
| PyTorch    | fp16 | 3.42 | **2.31** | 2.74 |
| TensorFlow | fp16 | 3.81 | 2.78 | 3.22 |
| JAX/Flax   | fp16 | 4.12 | 2.68 | 3.04 |
| ONNX (PyTorch export) | fp16 | – | 2.05 | 2.41 |
| TensorRT (PyTorch export) | fp16 | – | 1.62 | 1.89 |

**Takeaway**: For single-stream inference, exporting to ONNX or TensorRT beats native frameworks. Within native, PyTorch + `torch.compile(mode="max-autotune")` is fastest.

### 2.3 ViT-B/16, training throughput (samples/sec, batch=256, bf16, compiled)

| Framework  | Throughput | Peak GPU mem (MB) | GPU util |
|---|---|---|---|
| PyTorch    | 920  | 16412 | 87% |
| TensorFlow | 851  | 17084 | 84% |
| JAX/Flax   | **978** | 14920 | 91% |

**Takeaway**: Attention-heavy models favor JAX more than CNNs do; the XLA fusion of QKV projection + softmax + output projection cuts memory traffic.

### 2.4 Transformer (encoder-only, 6 layers, hidden=512, seq=128), throughput

| Framework  | Batch | Eager | Compiled |
|---|---|---|---|
| PyTorch    | 64 | 4811 | 6920 |
| TensorFlow | 64 | 4534 | 6240 |
| JAX/Flax   | 64 | 5102 | **7480** |

### 2.5 MLP baseline (4 hidden layers, 1024 units), throughput

| Framework  | Batch | Eager | Compiled |
|---|---|---|---|
| PyTorch    | 1024 | 121000 | 134000 |
| TensorFlow | 1024 | 112000 | 128000 |
| JAX/Flax   | 1024 | **142000** | **154000** |

**Takeaway**: For trivially parallelizable, compute-light networks, JAX has the largest lead — there's less code between you and the XLA compiler.

### 2.6 Tabular — XGBoost

XGBoost isn't comparable to the deep frameworks for the same workload. We benchmark it on the same tabular dataset (Higgs-1M, 28 features) using the GPU `hist` tree method.

| Method | Time/epoch (boost round) | Throughput (rows/sec) | Notes |
|---|---|---|---|
| XGBoost GPU hist | 0.48 s | 2.08M | depth 8 |
| XGBoost CPU hist (16 thr) | 6.14 s | 163K | |
| PyTorch MLP (fp16) | 2.71 s | 369K | comparable AUC after 50 epochs |
| LightGBM GPU | 0.41 s | 2.44M | reference only, not benchmarked here |

**Takeaway**: For tabular under ~10M rows and ~100 features, gradient-boosted trees dominate deep models on both speed and accuracy. Do not reach for PyTorch when XGBoost would do.

---

## 3. CPU-only results (16-thread EPYC)

### ResNet-50, training throughput (samples/sec, fp32)

| Framework  | Throughput |
|---|---|
| PyTorch (no compile) | 24.1 |
| PyTorch + `torch.compile` (inductor CPU) | 31.0 |
| TensorFlow + XLA CPU | 28.6 |
| JAX/Flax + jit | 27.8 |
| ONNX Runtime | 41.2 |

**Takeaway**: On CPU, the framework matters much less than the kernel implementation. Export to ONNX Runtime if you must serve CV on CPU.

### MLP, throughput (samples/sec)

| Framework  | Throughput |
|---|---|
| PyTorch | 18400 |
| TensorFlow | 16200 |
| JAX/Flax | **22900** |

---

## 4. Charts (described)

`mlbench report` generates these HTML charts. Below is what each chart conveys; the actual images live next to your JSON results.

1. **Training throughput by framework + batch size** — grouped bar chart, one cluster per model. Use this to spot which framework wins where, and which batch size each framework's win is largest at.
2. **Throughput vs batch size, log-log** — line chart per framework. The slope of this line indicates how well the framework exploits larger batches. Slope close to 1 = ideal scaling; flatter = compute-bound or framework overhead dominates.
3. **Inference latency CDF** — shows P50/P95/P99 visually. Use this when the choice is "do we accept higher P50 for a lower P99 tail?".
4. **Peak GPU memory vs throughput, scatter** — Pareto frontier of memory-vs-speed. Pick the framework on the frontier closest to your hardware budget.
5. **GPU utilization timeline** — per run, sampled from DCGM/`nvidia-smi`. Useful for spotting data-loading stalls (utilization dips in regular intervals = data-bound, not compute-bound).
6. **Compilation overhead waterfall** — for each compiled run, the first N iterations are dramatically slower. The chart shows how many warmup iters you need to amortize compilation. Helps decide whether `compile=True` is worth it for short jobs.

---

## 5. Reproducibility checklist

If you want your numbers to be comparable to the table above (within ±5%), you must control all of these:

- [ ] **Same GPU model and SKU**. A100 40 GB SXM4 ≠ A100 40 GB PCIe (NVLink vs PCIe limits some kernels).
- [ ] **Same CUDA + cuDNN versions**. cuDNN minor versions can shift convolution kernel selection 10-20%.
- [ ] **Same framework versions**. Pin in a venv. Don't run on the OS Python.
- [ ] **GPU clocks locked**. `nvidia-smi -lgc <base>,<boost>` before measurement; otherwise thermal throttling skews long runs.
- [ ] **No other GPU workloads**. `nvidia-smi --query-compute-apps=pid,used_memory --format=csv` should be empty.
- [ ] **Warmup**. 50 warmup iters min before measurement. Compilation kicks in late.
- [ ] **Determinism flags off for benchmarking**. `torch.backends.cudnn.benchmark = True` (auto-tunes kernels), `deterministic = False`. Determinism costs throughput.
- [ ] **Same dataset shape**. Synthetic (random tensors of declared shape) is the default and removes data-loading variance.
- [ ] **Same batch size**, including the "logical" batch size when using gradient accumulation.
- [ ] **Power capped consistently**. `nvidia-smi -pl 400` (or your card's max) so two runs on the same hardware don't differ because one was thermal-throttled.
- [ ] **Fixed seed**, but for shape-stability only — perf shouldn't depend on seed unless the model has data-dependent control flow.

---

## 6. What we deliberately do NOT measure

| Not measured | Why |
|---|---|
| Multi-node training | Out of scope for v0.3; see project-201 in senior track. |
| Distributed inference | Same reason. |
| Convergence quality | This is a perf benchmark, not an accuracy benchmark. Accuracy is dataset- and hyperparameter-dependent in ways that would dwarf framework differences. |
| Cold-start time | We benchmark steady-state. Add `--include-cold-start` if you need it. |
| Energy efficiency at the rack level | We only report `energy_joules` per run; PUE and HVAC are out of scope. |
| AMD GPUs | ROCm support is planned for v0.4. |

---

## 7. Comparing two runs

```bash
mlbench report --baseline results/run-baseline.json --candidate results/run-after-fix.json
```

Produces a delta table:

```text
                  Performance Delta
┏━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Framework  ┃ Model     ┃ Throughput Δ        ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ pytorch    │ resnet50  │ +12.4% ↑            │
│ tensorflow │ resnet50  │  -2.1% ↓ (noise)    │
│ jax        │ resnet50  │  +0.3% ≈            │
└────────────┴───────────┴─────────────────────┘
```

Delta ≤ 3% is treated as noise unless your hardware is unusually quiet.

---

## 8. Pointers

- For interpretation guidance (why JAX wins on transformers, when to prefer torch.compile, how to decide if a framework switch is worth it), see [ANALYSIS.md](./ANALYSIS.md).
- For implementation details, see [STEP_BY_STEP.md](../STEP_BY_STEP.md).
- To rerun the reference benchmarks: `mlbench run --config configs/comprehensive.yaml --output results/`.
