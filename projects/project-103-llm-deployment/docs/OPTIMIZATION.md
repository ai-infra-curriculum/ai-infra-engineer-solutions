# LLM Serving Optimization Playbook

A workflow-ordered guide to tuning the serving engine. Each section describes a single lever, the metric it moves, the cost/quality trade-off, and concrete numbers measured on the reference Llama-3.1-8B-Instruct / H100 80 GB SXM5 setup unless stated otherwise.

> Read the metrics section first. You cannot tune what you cannot measure.

## 1. Define your SLOs

Pick one set of SLOs and stop optimizing other dimensions once they are met. A typical chat product:

| SLO                              | Target                  | Why                                                       |
| -------------------------------- | ----------------------- | --------------------------------------------------------- |
| Time-to-first-token (TTFT) p95   | < 500 ms                | Perceived as "instant" by users                           |
| Inter-token latency (ITL) p95    | < 50 ms (≥ 20 tok/s)    | Reading-speed parity                                      |
| Error rate                       | < 0.1 %                 | Includes 5xx, timeouts, refusals                          |
| Throughput goodput               | ≥ 2500 output tok/s/GPU | The number that drives $/M tokens                         |

Batch/offline workloads invert these: throughput dominates, TTFT is irrelevant. Run them on a separate engine pool with different tuning.

## 2. Metrics you must collect

vLLM exposes a Prometheus endpoint at `/metrics`. The high-signal series:

| Metric                                | Meaning                                                     |
| ------------------------------------- | ----------------------------------------------------------- |
| `vllm:num_requests_running`           | Currently in-flight in the batch                            |
| `vllm:num_requests_waiting`           | Queue depth — leading indicator of overload                 |
| `vllm:gpu_cache_usage_perc`           | Fraction of KV blocks in use                                |
| `vllm:gpu_prefix_cache_hit_rate`      | Higher is free throughput                                   |
| `vllm:time_to_first_token_seconds`    | Histogram; alert on p95                                     |
| `vllm:time_per_output_token_seconds`  | Histogram; ITL                                              |
| `vllm:request_prompt_tokens`          | Input length distribution                                   |
| `vllm:request_generation_tokens`      | Output length distribution                                  |
| `vllm:request_success_total`          | Counter by `finish_reason`                                  |
| `DCGM_FI_DEV_GPU_UTIL`                | SM utilization (DCGM exporter)                              |
| `DCGM_FI_DEV_FB_USED`                 | HBM frame-buffer used                                       |
| `DCGM_FI_PROF_SM_ACTIVE`              | Real SM activity (more honest than `GPU_UTIL`)              |
| `DCGM_FI_PROF_DRAM_ACTIVE`            | HBM bandwidth utilization — decode is bound here            |

Run a synthetic benchmark on every config change. The de-facto tool is `vllm bench serve` (built into vLLM 0.6+) or the upstream `benchmarks/benchmark_serving.py` script.

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct --dtype bfloat16 \
  --max-model-len 8192 --max-num-seqs 256 \
  --gpu-memory-utilization 0.92 --enable-prefix-caching &

vllm bench serve \
  --backend vllm --model meta-llama/Llama-3.1-8B-Instruct \
  --dataset-name sharegpt --dataset-path ShareGPT_V3_unfiltered_cleaned_split.json \
  --num-prompts 1000 --request-rate 16
```

Report the four numbers that matter: TTFT p50/p95, ITL p95, output tokens/sec, request goodput.

## 3. Continuous batching tuning

Continuous batching (the default in vLLM and TGI) is the single biggest lever after model choice. Three flags interact:

| Flag                          | Effect                                                  | Starting point (H100 80 GB, 8B FP16) |
| ----------------------------- | ------------------------------------------------------- | ------------------------------------ |
| `--max-num-seqs`              | Hard concurrency cap                                    | 256                                  |
| `--max-num-batched-tokens`    | Token budget per forward pass (prefill + decode)        | 16384                                |
| `--enable-chunked-prefill`    | Splits long prefills across steps                       | on                                   |

Measured behavior on the reference setup (ShareGPT, 16 RPS, 1000 prompts):

| max-num-seqs | max-batched-tokens | TTFT p95 | ITL p95 | Output tok/s |
| ------------ | ------------------ | -------- | ------- | ------------ |
| 64           | 4096               | 220 ms   | 19 ms   | 1850         |
| 128          | 8192               | 290 ms   | 24 ms   | 3100         |
| 256          | 16384              | 410 ms   | 33 ms   | 4900         |
| 512          | 16384              | 720 ms   | 42 ms   | 5300         |
| 1024         | 32768              | 1450 ms  | 71 ms   | 5450         |

**Rules of thumb:**

1. Raise `max-num-seqs` until TTFT p95 just exits SLO; back off 20 %.
2. `max-num-batched-tokens` should be ≥ `max_model_len` for the longest realistic prompt so prefill is not stuck in a tiny budget.
3. Always enable `--enable-chunked-prefill` once you push `max-num-seqs > 64`; without it a single 30 k-token prompt freezes every other decoder for seconds.

## 4. Prefix caching

If your traffic has a stable system prompt or chat history, **turn it on**. It is the cheapest throughput win in the codebase.

```bash
--enable-prefix-caching
```

Reference workload: a customer-support chatbot with a 1200-token system prompt.

| Prefix caching | Output tok/s | TTFT p95 |
| -------------- | ------------ | -------- |
| Off            | 3100         | 480 ms   |
| On             | 4900         | 190 ms   |

The hit-rate metric `vllm:gpu_prefix_cache_hit_rate` should be > 0.6 for the win to materialize. If it sits near zero, your traffic does not share prefixes — find out why before assuming the feature is broken.

## 5. Quantization

Quantization reduces model weight size, increases throughput (more KV cache fits), and on Hopper FP8 also accelerates math. The trade-off is quality.

### 5.1 Format comparison (Llama-3.1-8B-Instruct on one H100 80 GB)

| Format        | Weight size | Output tok/s | MMLU 5-shot | GSM8K (CoT) | Notes                              |
| ------------- | ----------- | ------------ | ----------- | ----------- | ---------------------------------- |
| FP16 baseline | 16.0 GiB    | 4900         | 68.5        | 84.5        | Reference                          |
| BF16          | 16.0 GiB    | 4900         | 68.5        | 84.4        | Use this over FP16 on Hopper       |
| FP8 (E4M3)    |  8.5 GiB    | 7600         | 68.2        | 83.9        | Hopper-only; <0.5 pp regression    |
| INT8 (SmoothQuant) | 8.5 GiB | 6100        | 67.9        | 83.1        |                                    |
| AWQ INT4      |  4.5 GiB    | 5400         | 67.7        | 81.2        | Best 4-bit quality, Marlin kernel  |
| GPTQ INT4 (groupsize 128) | 4.5 GiB | 5300 | 67.1        | 79.8        | Older, slightly worse than AWQ     |
| GPTQ INT3     |  3.6 GiB    | 4800         | 64.8        | 72.4        | Visible quality drop — avoid       |

`MMLU` regression < 1 pp is usually invisible to users; > 2 pp is felt. GSM8K is the canary for math/reasoning loss.

### 5.2 When to pick each

- **FP8 (E4M3)** on H100/H200 for production. Highest throughput, smallest quality cost, supported natively by vLLM and TRT-LLM. Activations also quantized; calibrate with `llm-compressor` (`oneshot --recipe fp8.yaml`).
- **AWQ INT4** when you must fit a 70B on a single 80 GB GPU, or to double the KV budget on 8B. The Marlin kernel makes it actually faster than FP16 on Ampere; on Hopper FP8 still wins.
- **BF16** as the safe default if you do not yet have a calibration set.
- **GPTQ** only when AWQ does not exist for your architecture.

### 5.3 Calibration

Quantization quality depends on the calibration dataset matching your traffic distribution. Use 256-512 samples that resemble production prompts. Do NOT use C4 or WikiText for an instruction-tuned chat model — quality regression on instruction following will be 2-3x worse than the table above.

```bash
python -m llmcompressor.transformers.compression.calibrate \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --dataset /data/calibration/customer_support_samples.jsonl \
  --recipe configs/fp8_per_tensor.yaml \
  --num-calibration-samples 512 \
  --output-dir /weights/llama-3.1-8b-fp8
```

After calibration, re-run your eval harness (MMLU, GSM8K, plus a domain-specific eval) and gate the release on ≤1 pp regression.

## 6. Speculative decoding

Speculative decoding runs a small "draft" model to produce N candidate tokens, then verifies them in one forward pass of the target model. Net effect: 1.5-3x decode throughput for greedy or low-temperature generation.

vLLM flags:

```bash
--speculative-model meta-llama/Llama-3.2-1B-Instruct \
--num-speculative-tokens 5 \
--use-v2-block-manager
```

Reference numbers (Llama-3.1-70B target, Llama-3.2-1B draft, both BF16, 4× H100 TP):

| Config              | Decode tok/s | TTFT p95 | Cost per M output tokens |
| ------------------- | ------------ | -------- | ------------------------ |
| Greedy, no spec dec | 41           | 720 ms   | $4.20                    |
| Spec dec, k=3       | 78           | 740 ms   | $2.25                    |
| Spec dec, k=5       | 92           | 760 ms   | $1.95                    |
| Spec dec, k=7       | 88           | 790 ms   | $2.05                    |

**Caveats:**

- Acceptance rate drops at high temperature (`>0.7`). Speculative decoding is mostly useless for creative-writing workloads.
- The draft model consumes HBM too; budget for it.
- EAGLE-2 / Medusa heads outperform a separate draft model when they exist for your target. They train in hours on a single H100 and lift acceptance from ~0.5 to ~0.7.

## 7. Tensor parallel sizing for large models

For models that do not fit on one GPU, `--tensor-parallel-size` shards each layer across `N` GPUs. All-reduce after every attention and MLP block — the inter-GPU bandwidth determines whether this is fast or slow.

Llama-3.1-70B BF16 throughput by TP and interconnect:

| TP   | Interconnect      | Output tok/s | TTFT p95 | $/M tokens (on-demand H100) |
| ---- | ----------------- | ------------ | -------- | --------------------------- |
| TP=2 | NVLink (HGX H100) | 1850         | 510 ms   | $5.20                       |
| TP=2 | PCIe Gen5         | 920          | 980 ms   | $10.50                      |
| TP=4 | NVLink            | 2900         | 410 ms   | $6.65                       |
| TP=4 | PCIe              | 1100         | 1450 ms  | $17.40                      |
| TP=8 | NVLink            | 3600         | 380 ms   | $10.70                      |

**Heuristics:**

- Never run TP > 1 across PCIe nodes unless you have no alternative. NVLink is non-optional for 70B+.
- Going from TP=4 to TP=8 doubles cost and adds <25% throughput on most models; only do it for the latency win.
- Combine TP within a node with PP across nodes for 400B+ models (`--pipeline-parallel-size 2 --tensor-parallel-size 8`).

## 8. KV cache sizing and `gpu_memory_utilization`

vLLM grabs `gpu_memory_utilization * total_HBM` and uses what is left after weights and activations for KV cache. Default 0.90 is conservative; 0.92-0.95 on dedicated nodes is fine.

Tradeoff:

- Higher utilization → more KV blocks → more concurrent sequences → throughput rises.
- Too high → OOM on a prompt-length spike → engine crash, pod restart.

Calculate a safe ceiling using the KV-per-token formula from [ARCHITECTURE.md](ARCHITECTURE.md). Leave at least `peak_concurrent_sequences * max_model_len * bytes_per_token` of slack.

## 9. Attention backend choice

vLLM supports multiple attention kernels. Pick by hardware:

| Backend       | Hardware            | Notes                                       |
| ------------- | ------------------- | ------------------------------------------- |
| `FLASHINFER`  | Hopper, Ada         | Fastest on H100; preferred default          |
| `FLASH_ATTN`  | Ampere, Hopper      | Mature fallback                             |
| `XFORMERS`    | Anywhere CUDA       | Slowest; use only for debugging             |
| `TORCH_SDPA`  | CPU / AMD ROCm      | Required for non-CUDA                       |

```bash
export VLLM_ATTENTION_BACKEND=FLASHINFER
```

Switching from `FLASH_ATTN` to `FLASHINFER` on H100 lifts decode throughput ~12-18% on long contexts.

## 10. CUDA graphs

vLLM compiles CUDA graphs for the common decode shapes. Side effects:

- Adds 30-60 s to startup.
- Memory cost ~1-2 GiB.
- Decode latency drops ~10-20% by eliminating launch overhead.

Disable with `--enforce-eager` only when debugging a hang — never in production.

## 11. End-to-end recipes

### Recipe A — Low-latency chat (TTFT-sensitive)

```bash
--model meta-llama/Llama-3.1-8B-Instruct
--dtype bfloat16
--max-num-seqs 96
--max-num-batched-tokens 8192
--enable-chunked-prefill
--enable-prefix-caching
--gpu-memory-utilization 0.90
```

Expect: TTFT p95 ~210 ms, output ~3500 tok/s, $1.10 per M output tokens at on-demand p5.48xlarge.

### Recipe B — High-throughput batch (offline summarization, embedding generation, etc.)

```bash
--model meta-llama/Llama-3.1-8B-Instruct
--dtype bfloat16
--max-num-seqs 512
--max-num-batched-tokens 16384
--enable-chunked-prefill
--gpu-memory-utilization 0.95
--disable-log-requests
```

Expect: TTFT irrelevant, output ~5400 tok/s, $0.70 per M output tokens.

### Recipe C — 70B production chat

```bash
--model meta-llama/Llama-3.1-70B-Instruct
--quantization fp8   # if you have calibrated weights
--tensor-parallel-size 4
--max-num-seqs 128
--max-num-batched-tokens 8192
--enable-prefix-caching
--enable-chunked-prefill
--speculative-model meta-llama/Llama-3.2-1B-Instruct
--num-speculative-tokens 5
--gpu-memory-utilization 0.92
```

Expect: TTFT p95 ~480 ms, output ~3600 tok/s aggregate, $1.95 per M output tokens.

## 12. Order of operations when latency regresses

1. Read `vllm:num_requests_waiting`. > 0 sustained → you are CPU-/GPU-overloaded, not latency-tuned. Scale out.
2. Read `vllm:gpu_cache_usage_perc`. > 0.95 → KV cache thrashing; reduce `max-num-seqs`.
3. Read `vllm:gpu_prefix_cache_hit_rate`. If it dropped, a deployed prompt template changed and broke sharing.
4. Read `DCGM_FI_PROF_DRAM_ACTIVE`. If pinned near 100% → decode is memory-bandwidth-bound; FP8/quantization is the only lever left.
5. Read input length distribution (`vllm:request_prompt_tokens` histogram). A regression in prompt length explodes prefill cost; spot the change and shorten prompts.

## 13. Anti-patterns

- **Tuning batch size against synthetic uniform prompts.** Real distributions are heavy-tailed. Use ShareGPT or your own captured traffic.
- **Maximizing GPU utilization as a goal.** Decode is memory-bandwidth-bound — you can be at 99% `GPU_UTIL` and still leave throughput on the table. Watch `DRAM_ACTIVE` and `SM_ACTIVE` instead.
- **Setting `--enforce-eager` "just to be safe".** You give up 10-20% decode for no reason.
- **Quantizing without an eval gate.** Quality regressions are silent until customers complain.
- **One engine pod per request type.** Run separate pools for low-latency and high-throughput traffic.

## 14. Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — KV-cache math and engine internals
- [COST.md](COST.md) — turning tok/s into dollars
- [GPU.md](GPU.md) — when more GPU beats more tuning
