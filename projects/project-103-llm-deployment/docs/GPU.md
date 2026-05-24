# GPU Selection and Sizing Guide

How to pick the right GPU and how many of them you need to run a given model in production. Covers the memory model, the interconnect choice, the SKU comparison, MIG for multi-tenant, and how to size for real traffic.

## 1. The memory math

Total HBM required at inference:

```
HBM_required  ≈  model_weights
              +  KV_cache_peak
              +  activations
              +  CUDA / cuBLAS workspace
              +  fragmentation slack
```

### 1.1 Model weights

```
weight_bytes = num_parameters × bytes_per_parameter
```

| Precision      | Bytes per parameter | Notes                              |
| -------------- | ------------------- | ---------------------------------- |
| FP32           | 4                   | Almost never used at inference     |
| FP16 / BF16    | 2                   | Default                            |
| FP8 (E4M3/E5M2)| 1                   | Hopper+; close-to-FP16 quality     |
| INT8           | 1                   | SmoothQuant / weight-only          |
| INT4 (AWQ/GPTQ)| 0.5                 | + ~16 bytes per group of overhead  |

Worked numbers:

| Model                | FP16   | FP8    | INT8   | INT4 (AWQ) |
| -------------------- | ------ | ------ | ------ | ---------- |
| Llama-3.2-1B         | 2.0 GB | 1.0 GB | 1.0 GB | 0.6 GB     |
| Llama-3.2-3B         | 6.0 GB | 3.0 GB | 3.0 GB | 1.7 GB     |
| Llama-3.1-8B         | 16 GB  | 8.0 GB | 8.0 GB | 4.5 GB     |
| Llama-3.1-70B        | 140 GB | 70 GB  | 70 GB  | 35-40 GB   |
| Mixtral-8x22B (141B params, 39B active) | 280 GB | 140 GB | 140 GB | 75 GB |
| Llama-3.1-405B       | 810 GB | 405 GB | 405 GB | 200 GB     |

### 1.2 KV cache

```
KV_per_token = 2 × num_layers × num_kv_heads × head_dim × dtype_bytes
KV_peak      = KV_per_token × max_concurrent_sequences × avg_sequence_length
```

For Llama-3.1-8B (32 layers, 8 KV heads via GQA, 128 head dim, FP16): **128 KiB per token**.
For Llama-3.1-70B (80 layers, 8 KV heads, 128 head dim, FP16): **320 KiB per token**.
For Llama-3.1-405B (126 layers, 8 KV heads, 128 head dim, FP16): **504 KiB per token**.

Examples at 4096-token average sequence:

| Model | KV per sequence | KV for 64 concurrent | KV for 256 concurrent |
| ----- | --------------- | -------------------- | --------------------- |
| 8B    | 0.5 GB          | 32 GB                | 128 GB                |
| 70B   | 1.3 GB          | 83 GB                | 332 GB                |
| 405B  | 2.0 GB          | 128 GB               | 512 GB                |

KV cache can be quantized to FP8 (vLLM `--kv-cache-dtype fp8`) halving these numbers with minimal quality loss.

### 1.3 Activations and workspace

Rough rule of thumb: **2-6 GiB** for activations plus 1-2 GiB for cuBLAS / cuDNN workspace at typical batch sizes. PagedAttention reduces activation overhead significantly compared to vanilla FlashAttention.

### 1.4 Fragmentation slack

PagedAttention practically eliminates this. With non-paged attention, plan for 10-20% wasted HBM.

### 1.5 Putting it together

Llama-3.1-8B BF16, target 128 concurrent sequences × 4096 avg tokens, on one H100 80 GB:

```
16 GB (weights) + 64 GB (KV) + 4 GB (act) + 2 GB (workspace) = 86 GB → does not fit!
```

Options: reduce concurrency to 96 (48 GB KV → 70 GB total, fits), quantize KV to FP8 (32 GB KV → 54 GB total, comfortable), or quantize model to FP8 (8 GB weights → 78 GB total fits).

## 2. SKU comparison

### 2.1 Datacenter GPUs that matter for LLM serving

| GPU         | HBM   | HBM type | HBM BW    | FP16 TFLOPS (dense) | FP8 TFLOPS (dense) | Form factor | NVLink | TDP   |
| ----------- | ----- | -------- | --------- | ------------------- | ------------------ | ----------- | ------ | ----- |
| L4          | 24 GB | GDDR6    | 300 GB/s  | 121                 | 242                | PCIe        | No     | 72 W  |
| L40S        | 48 GB | GDDR6    | 864 GB/s  | 362                 | 733                | PCIe        | No     | 350 W |
| A10G        | 24 GB | GDDR6    | 600 GB/s  | 125                 | n/a                | PCIe        | No     | 150 W |
| A100 40 GB  | 40 GB | HBM2e    | 1555 GB/s | 312                 | n/a                | SXM/PCIe    | NVLink | 400 W |
| A100 80 GB  | 80 GB | HBM2e    | 2039 GB/s | 312                 | n/a                | SXM/PCIe    | NVLink | 400 W |
| H100 80 GB SXM | 80 GB | HBM3  | 3350 GB/s | 989                 | 1979               | SXM5        | NVLink 4 | 700 W |
| H100 PCIe   | 80 GB | HBM3     | 2039 GB/s | 756                 | 1513               | PCIe        | Bridge | 350 W |
| H200 SXM    | 141 GB| HBM3e    | 4800 GB/s | 989                 | 1979               | SXM5        | NVLink 4 | 700 W |
| B200 SXM    | 192 GB| HBM3e    | 8000 GB/s | 2250                | 4500 (FP4 9000)    | SXM6        | NVLink 5 | 1000 W |

**The two numbers that matter for LLM serving are HBM capacity and HBM bandwidth.** Inference is memory-bandwidth-bound during decode and capacity-bound during model loading. Compute matters mostly for prefill on long contexts.

### 2.2 Decision matrix

| You want to serve...                          | Pick                                            | Why                                                 |
| --------------------------------------------- | ----------------------------------------------- | --------------------------------------------------- |
| 1-3B model, low QPS, edge / batch             | L4                                              | Cheapest, low power, fits 3B BF16 + KV              |
| 7-8B model, low-mid QPS                       | A10G or L4 if budget-constrained                | Sweet spot per dollar; L40S if you need FP8         |
| 7-13B production chat at scale                | H100 (FP8)                                      | 5-7x cheaper per token than A10G                    |
| 13-30B model                                  | L40S (48 GB) or H100                            | L40S fits 30B AWQ; H100 fits in BF16 with KV        |
| 70B model, single-GPU                         | H100 80 GB with AWQ INT4                        | Survives 1 GPU; lower throughput than TP            |
| 70B model, throughput                         | 2× H200 (TP=2) or 4× H100 (TP=4)                | H200 wins unit economics; H100 wins availability    |
| 100-200B MoE (Mixtral-8x22B)                  | 4-8× H100 SXM with TP=4                         | Need NVLink for active-expert routing               |
| 405B model                                    | 8× H200 SXM, FP8, TP=8                          | Only sane single-node setup                         |
| 405B model, on H100 only                      | 16× H100 with TP=8 + PP=2                       | Two nodes; PP adds 50-150 ms TTFT                   |
| Multi-tenant model serving (small models)     | A100 or H100 with MIG                           | Hardware-partitioned isolation                      |
| Embedding / reranker only                     | L4 or T4 with TEI/FastEmbed                     | Don't waste H100 cycles                             |

### 2.3 Pitfalls

- **L4 has GDDR6, not HBM.** Its memory bandwidth (300 GB/s) is 10x slower than H100. Fine for batch/embedding, painful for chat decoding past 7B.
- **A10G is Ampere, FP8 not supported.** If your strategy depends on FP8, A10G is a dead end.
- **A100 40 GB cannot hold a 70B model.** Period. Don't try.
- **H100 PCIe is not the same chip as H100 SXM.** PCIe has lower TDP, lower clocks, no NVLink (just a 600 GB/s bridge between pairs). Avoid for TP>2.

## 3. NVLink vs PCIe

For tensor parallel across N GPUs, the engine performs `all_reduce` after every attention and MLP block. Bandwidth matters disproportionately:

| Interconnect                  | Bandwidth (per GPU pair)    | TP=8 effective for Llama-70B BF16 |
| ----------------------------- | --------------------------- | --------------------------------- |
| PCIe Gen4 x16                 | 32 GB/s bidir               | 35-50% of theoretical             |
| PCIe Gen5 x16                 | 64 GB/s bidir               | 50-65%                            |
| NVLink 3 bridge (H100 PCIe)   | 600 GB/s                    | 75%                               |
| NVLink 4 (H100 SXM, HGX)      | 900 GB/s (per GPU aggregate)| 90-95%                            |
| NVSwitch (HGX 8-way)          | full all-to-all 900 GB/s    | 95%+                              |

**Practical rule:** never run TP > 2 over PCIe in production. Throughput drops 2-4x. Use NVLink-equipped HGX nodes (`p5.48xlarge`, `a3-highgpu-8g`, `Standard_ND96isr_H100_v5`).

Cross-node TP is even worse:
- **InfiniBand 400 Gbit (NDR):** ~50 GB/s per link, even 8x NIC bonds don't reach NVLink speeds.
- **AWS EFA:** ~50 GB/s aggregate per p5 instance; OK for pipeline parallel (PP), wrong for TP.

The 405B at FP8 on 8× H200 fits in a single NVLink domain, which is why everyone targets HGX. The moment you cross the node boundary, you take a real latency penalty and you need to use **pipeline parallel** (`--pipeline-parallel-size`) for the cross-node split.

## 4. MIG for multi-tenant

Multi-Instance GPU (MIG) hardware-partitions an A100 or H100 into up to 7 isolated slices. Each slice has its own SMs, L2, HBM, and memory bandwidth — true isolation, not just MPS.

H100 80 GB MIG profiles:

| Profile      | Compute slice | HBM   | Use case                                              |
| ------------ | ------------- | ----- | ----------------------------------------------------- |
| 1g.10gb      | 1/7           | 10 GB | Small models (≤3B), embeddings                        |
| 2g.20gb      | 2/7           | 20 GB | 7B AWQ INT4, embeddings batch                         |
| 3g.40gb      | 3/7           | 40 GB | 7-13B BF16                                            |
| 4g.40gb      | 4/7           | 40 GB | 7-13B BF16 with more compute                          |
| 7g.80gb      | full          | 80 GB | Same as no MIG                                        |

**When MIG makes sense:**

- Multi-tenant serving where small models from different customers must be isolated.
- Mixing inference + a small batch job on the same GPU without QoS interference.
- Compliance regimes that require hardware isolation.

**When MIG is wrong:**

- Single big model — MIG cannot span multiple slices in one process.
- High-throughput single-tenant serving — overhead from non-shared L2 reduces effective throughput 10-20% vs full GPU.
- Frequent reconfiguration — switching MIG profiles drains the device and takes ~30 s.

Configure with the GPU Operator:

```yaml
# values for nvidia/gpu-operator
mig:
  strategy: mixed   # allow per-node profile selection
migManager:
  enabled: true
  config:
    name: default-mig-parted-config
    default: all-1g.10gb
```

Then label nodes:

```bash
kubectl label node gpu-node-01 nvidia.com/mig.config=all-2g.20gb --overwrite
```

Pods request slices via the same resource name:

```yaml
resources:
  limits:
    nvidia.com/mig-2g.20gb: 1
```

## 5. Sizing by traffic

How many GPUs to provision is a function of throughput per GPU × utilization × replicas-for-redundancy.

```
gpus_needed = ceil(
    peak_tokens_per_second_required
    / measured_tokens_per_second_per_gpu
    / target_utilization
)
add_for_redundancy = max(1, ceil(gpus_needed × 0.25))
total = gpus_needed + add_for_redundancy
```

Example: 50 RPS sustained, 256-token median output, Llama-3.1-8B FP8 on H100 (7600 tok/s):

```
tok/s required = 50 × 256 = 12,800
gpus_needed    = ceil(12800 / 7600 / 0.6) = 3
+25% headroom  = 1 more
total          = 4 H100 (one HGX node)
```

For peak burst handling, autoscale to 2x baseline (see [DEPLOYMENT.md §6](DEPLOYMENT.md)).

## 6. Edge GPUs

For edge and on-prem inference at small scale:

| GPU             | HBM/VRAM | Use case                                  |
| --------------- | -------- | ----------------------------------------- |
| RTX 4090        | 24 GB    | Single-developer; 7-13B AWQ; not for prod |
| RTX 6000 Ada    | 48 GB    | Workstation; 30B AWQ; small office serving|
| L4              | 24 GB    | Edge serving, low-power racks             |
| Jetson AGX Orin | 64 GB    | Truly edge; quantized 7B at slow rate     |

Don't use consumer-class (RTX) GPUs in production datacenters — no ECC, no SR-IOV, NVIDIA EULA prohibits it for many use cases, and there is no driver support story for Kubernetes at scale.

## 7. GPU health and lifecycle

Things that kill GPUs over time, in rough order of likelihood:

1. **Thermal throttling** from poor airflow → check `DCGM_FI_DEV_GPU_TEMP`, alert > 85 °C, hard-fail >95 °C.
2. **Memory ECC errors** → `DCGM_FI_DEV_ECC_DBE_VOL_TOTAL` should stay 0. A single DBE means RMA.
3. **Xid events** → 79 (GPU fell off bus), 31 (mem fault), 13 (graphics engine error). Drain the node and replace.
4. **PCIe link degradation** → `nvidia-smi -q | grep "PCIe Generation"` should match expected gen; downgrade = bad slot or cable.
5. **HBM bit flips on stress** → run `dcgmi diag -r 3` weekly during low-traffic windows.

Standard SRE practice: every GPU node runs DCGM exporter, ships metrics to Prometheus, and has an alert that drains and cordons the node on the first DBE or repeated Xid.

## 8. Future-proofing

- **B200 / B300 (Blackwell)** ships in volume Q3 2025-Q1 2026. FP4 native, 192-288 GB HBM, NVLink 5 at 1800 GB/s. **Plan for FP4 in your quantization pipeline** so you can adopt without re-engineering.
- **GB200 NVL72** rack-scale unit: 72 GPUs in a single NVLink domain. Will reshape how you think about TP/PP for 1T+ models.
- **AMD MI300X (192 GB HBM3)** is a real alternative for capacity-bound workloads (405B in BF16 fits on 5 GPUs vs 8 H100s). Software stack (ROCm + vLLM) is mature enough for production as of 2025; CUDA is still smoother day-to-day.
- **Inferentia / TPU / Gaudi** are viable for specific high-volume models; the porting cost is real. Evaluate only when you have ≥$1M/month NVIDIA spend that survives a 30% discount on a port.

## 9. Procurement checklist before you buy

- [ ] Memory math worked for your target model × precision × concurrency
- [ ] NVLink topology verified for any TP > 1
- [ ] PCIe generation and lane count verified
- [ ] Driver version compatibility with the CUDA in your container
- [ ] DCGM exporter and Xid alerting configured pre-day-one
- [ ] ECC enabled (datacenter GPUs only — consumer cards lack ECC)
- [ ] Cluster-autoscaler / NodePool limits set so you don't accidentally autoscale to $100k overnight
- [ ] Spot vs on-demand decision aligned with workload SLO (see [COST.md](COST.md))

## 10. Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — engine internals and KV math
- [COST.md](COST.md) — turning GPU hours into dollars
- [OPTIMIZATION.md](OPTIMIZATION.md) — getting more tokens per GPU
- [DEPLOYMENT.md](DEPLOYMENT.md) — wiring GPUs into Kubernetes
