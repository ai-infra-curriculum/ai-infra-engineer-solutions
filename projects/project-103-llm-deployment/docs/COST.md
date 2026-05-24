# LLM Serving Cost Analysis

This document derives **dollars per million tokens** from first principles for the models supported by this platform, compares purchasing options, and gives a reproducible calculator. Numbers reflect public AWS pricing in Q2 2026 unless noted. Update the assumptions and re-derive; do not treat the totals as gospel.

## 1. The only formula you need

```
$ per 1M output tokens =  (GPU instance hourly cost / 3600)
                        × 1,000,000
                        / measured_output_tokens_per_second_per_instance
```

Everything else is sourcing the two inputs honestly. The denominator must be **goodput** measured under your traffic distribution, not peak synthetic throughput.

## 2. Reference instance pricing (us-east-1, on-demand)

| Instance        | GPUs            | HBM total | NVLink | Hourly on-demand | 3-yr reserved (no upfront) | Spot (typical)   |
| --------------- | --------------- | --------- | ------ | ---------------- | -------------------------- | ---------------- |
| g6.12xlarge     | 4× L4 (24 GB)   | 96 GB     | No     | $4.91            | $2.62                      | $1.20-$1.80      |
| g5.12xlarge     | 4× A10G (24 GB) | 96 GB     | No     | $5.67            | $2.75                      | $1.50-$2.20      |
| g5.48xlarge     | 8× A10G         | 192 GB    | No     | $16.29           | $7.45                      | $5.00-$7.00      |
| p4d.24xlarge    | 8× A100 40 GB   | 320 GB    | NVLink | $32.77           | $13.10                     | $9-$15           |
| p4de.24xlarge   | 8× A100 80 GB   | 640 GB    | NVLink | $40.96           | $16.40                     | $12-$20          |
| p5.48xlarge     | 8× H100 80 GB   | 640 GB    | NVLink | $98.32           | $44.80                     | $28-$55          |
| p5e.48xlarge    | 8× H200 141 GB  | 1128 GB   | NVLink | $122.40          | $55.10                     | (limited supply) |
| p5en.48xlarge   | 8× H200 141 GB + faster network | 1128 GB | NVLink | $128.40 | $58.20            | (limited supply) |

Single-GPU price (divide by 8 for SXM nodes):

| Per-GPU         | Hourly on-demand |
| --------------- | ---------------- |
| L4              | $1.23            |
| A10G            | $2.04            |
| A100 80 GB      | $5.12            |
| H100 80 GB SXM  | $12.29           |
| H200 141 GB SXM | $15.30           |

Other clouds are within ±15%. GCP A3 (H100) is $11.85/GPU-hour on-demand and Azure ND-H100-v5 is $12.50. **Use whatever your committed-use discounts are; the structure below does not change.**

## 3. Measured throughput per model

From [OPTIMIZATION.md](OPTIMIZATION.md) reference workload (ShareGPT-like, 256 input tokens median, 256 output tokens median, vLLM 0.6+ default tuning, BF16 unless noted). Numbers are **aggregate output tokens/sec per node**.

| Model              | Hardware             | Precision | Aggregate tok/s | Per-GPU tok/s |
| ------------------ | -------------------- | --------- | --------------- | ------------- |
| Llama-3.1-8B       | 1× L4 (24 GB)        | BF16      | 380             | 380           |
| Llama-3.1-8B       | 1× A10G (24 GB)      | BF16      | 720             | 720           |
| Llama-3.1-8B       | 1× A100 80 GB        | BF16      | 2400            | 2400          |
| Llama-3.1-8B       | 1× H100 80 GB        | BF16      | 4900            | 4900          |
| Llama-3.1-8B       | 1× H100 80 GB        | FP8       | 7600            | 7600          |
| Llama-3.1-8B       | 1× L40S (48 GB)      | BF16      | 1850            | 1850          |
| Llama-3.1-70B      | 4× H100 80 GB (TP=4) | BF16      | 2900            | 725           |
| Llama-3.1-70B      | 4× H100 80 GB (TP=4) | FP8       | 4400            | 1100          |
| Llama-3.1-70B      | 1× H100 80 GB        | AWQ INT4  | 1350            | 1350          |
| Llama-3.1-70B      | 2× H200 141 GB (TP=2)| FP8       | 5100            | 2550          |
| Llama-3.1-405B     | 8× H100 80 GB (TP=8) | FP8       | 1850            | 230           |
| Llama-3.1-405B     | 8× H200 141 GB (TP=8)| FP8       | 2900            | 360           |

Caveats:

- Input/output ratio matters. Prefill-heavy traffic (RAG with 4k-token context, 100-token answer) costs 2-4x per output token compared to chat. Re-measure on your own data.
- Streaming (single user feel) vs batch (sweep over a dataset) can shift goodput 2x in either direction.
- Speculative decoding can lift the 70B numbers another 30-80%; not included above to keep the table apples-to-apples.

## 4. $ per million tokens — derived

### 4.1 Llama-3.1-8B-Instruct

| Setup                     | $/GPU-hr | Per-GPU tok/s | $/M output tokens | $/M input tokens (rough) |
| ------------------------- | -------- | ------------- | ----------------- | ------------------------ |
| L4, on-demand             | $1.23    | 380           | $0.90             | $0.18                    |
| A10G, on-demand           | $2.04    | 720           | $0.79             | $0.16                    |
| A100 80 GB, on-demand     | $5.12    | 2400          | $0.59             | $0.12                    |
| H100, on-demand, BF16     | $12.29   | 4900          | $0.70             | $0.14                    |
| H100, on-demand, FP8      | $12.29   | 7600          | $0.45             | $0.09                    |
| H100, 3-yr reserved, FP8  | $5.60    | 7600          | $0.20             | $0.04                    |
| H100, spot, FP8           | $4.50    | 7600          | $0.16             | $0.03                    |

"$/M input tokens" assumes input is ~5x cheaper than output for chat traffic because prefill batches efficiently and is amortized across many output tokens. Verify against your own data.

**Punchline:** the best 8B production setup is FP8 on H100 with continuous batching. Going from BF16 to FP8 cuts cost in half. Going from on-demand to a 3-yr reservation cuts it by another 2.3x. **Spot is even cheaper but only suitable for batch workloads** — see §6.

### 4.2 Llama-3.1-70B-Instruct

| Setup                                  | $/node-hr | Node tok/s | $/M output tokens |
| -------------------------------------- | --------- | ---------- | ----------------- |
| p5.48xlarge, BF16, TP=4 (uses 4 GPUs)  | $49.16    | 2900       | $4.71             |
| p5.48xlarge, FP8, TP=4                 | $49.16    | 4400       | $3.10             |
| p5.48xlarge, FP8, TP=4, spec-decode    | $49.16    | 6200       | $2.20             |
| 1× H100 AWQ INT4 (single GPU rental)   | $12.29    | 1350       | $2.53             |
| p5.48xlarge, FP8, 3-yr reserved        | $22.40    | 4400       | $1.41             |
| p5.48xlarge, FP8, spot                 | $16.00    | 4400       | $1.01             |
| p5e.48xlarge, FP8, TP=2 (uses 2 GPUs)  | $30.60    | 5100       | $1.67             |

The H200 row matters: when 70B FP8 fits comfortably on 2 GPUs (vs 4 H100), you halve the GPU count and only pay ~25% more per GPU-hour. **H200 is the better unit economics for 70B.**

### 4.3 Llama-3.1-405B-Instruct

| Setup                                  | $/node-hr | Node tok/s | $/M output tokens |
| -------------------------------------- | --------- | ---------- | ----------------- |
| p5.48xlarge, FP8, TP=8                 | $98.32    | 1850       | $14.77            |
| p5e.48xlarge, FP8, TP=8                | $122.40   | 2900       | $11.72            |
| p5.48xlarge, FP8, 3-yr reserved        | $44.80    | 1850       | $6.73             |
| p5e.48xlarge, FP8, 3-yr reserved       | $55.10    | 2900       | $5.27             |
| 2× p5.48xlarge, FP8, TP=8 + PP=2       | $196.64   | 2400       | $22.77            |

**Punchline:** at the 405B tier, you are paying $5-15/M tokens. Compare to OpenAI / Anthropic API pricing: GPT-4o-class APIs at ~$10/M output. Self-hosting 405B only pencils if you have load that justifies a full reserved node (~$330k/yr per p5e) and a workload that the frontier APIs cannot serve (data residency, fine-tunes, custom safety policies).

## 5. On-demand vs spot vs reserved

| Purchase option            | Discount vs on-demand | Interruption risk | When to use                                                 |
| -------------------------- | --------------------- | ----------------- | ----------------------------------------------------------- |
| On-demand                  | 0%                    | None              | Steady-state serving, no commitment yet, sub-3-month traffic |
| 1-yr reserved (CUD/RI/SP)  | 30-45%                | None              | Confirmed baseline                                          |
| 3-yr reserved (no upfront) | 50-60%                | None              | Multi-year contract                                         |
| 3-yr reserved (all upfront)| 55-65%                | None              | Cash-rich; willing to lock in NVIDIA generation             |
| Savings Plans (compute)    | 40-65%                | None              | Flexible across instance families                           |
| Spot / Preemptible         | 60-90%                | 2-minute warning  | Batch jobs, async pipelines, training restarts              |
| Capacity Blocks (AWS)      | varies                | Reserved windows  | Time-boxed training or eval runs                            |

**Mixed strategy that actually works in production:**

1. Buy 3-yr reservations (or Savings Plans) for **P50 of your traffic** — the load you have at 3 AM on a Tuesday.
2. Add on-demand for **P50 → P90** burst — peak business hours, marketing campaigns.
3. Run batch / async workloads on **spot** with checkpoint-restart and a separate queue.
4. Keep training and eval workloads on **spot or capacity blocks**, never on the serving reservation.

A real account with 30% baseline / 50% peak / 20% batch usually ends up around 45-55% blended discount vs all-on-demand.

## 6. Spot eligibility decision

Spot is great for batch, terrible for live serving of stateful engines. Decision rule:

```
Can the workload tolerate a 2-minute eviction warning and restart-from-zero?

  Yes → spot pool with checkpointing.
  No  → on-demand or reserved.
```

- **Embeddings generation, classification, summarization sweeps** → spot.
- **Async batch completions API** with retries → spot.
- **Synchronous chat product** → never spot.
- **RAG ingestion / re-embedding** → spot.

For the live serving pool, you can still tolerate occasional spot in a small fraction of replicas if your PDB and queueing model can absorb it — typically not worth the operational headache. Real production teams keep serving on on-demand/reserved and reserve spot for batch.

## 7. Batch vs streaming economics

Batch (offline) workloads use the GPU 2-4x more efficiently than chat-style streaming. Reasons:

- No idle time waiting for a slow human user.
- All sequences are long → fewer scheduler stalls.
- You can pump `max-num-seqs` to 512+ without hurting any TTFT SLO.

| Workload type        | Effective tok/s, H100 FP8 8B | $/M tokens (on-demand) |
| -------------------- | ---------------------------- | ---------------------- |
| Streaming chat (P50 user) | 4500                    | $0.75                  |
| Bulk batch completion     | 9800                    | $0.35                  |
| Async API (lenient SLOs)  | 7100                    | $0.48                  |

If your product can move part of its traffic from streaming to batch (e.g. nightly content generation, async summaries), do it. The cost ratio is 2x.

## 8. Hidden costs people forget

| Cost                              | Typical magnitude (mid-size deployment)           |
| --------------------------------- | -------------------------------------------------- |
| Egress (responses to clients)     | $0.05-$0.09 per GB; $30-200/month for chat        |
| Object storage of model weights   | $0.023/GB-month → $50-500/month for a model zoo   |
| EBS gp3 for staging               | $0.08/GB-month + $0.005 per IOPS                  |
| EFS / FSx for shared weights      | $0.30-$1.40/GB-month — easy to spend $1000+/month |
| Cross-AZ data transfer            | $0.01/GB each direction — adds up with HPA        |
| Inter-region replication          | $0.02/GB                                          |
| Cloud load balancer (ALB)         | ~$25/month + $0.008 per LCU-hr                    |
| NAT gateway egress for pulls      | $0.045/GB processed                               |
| CloudWatch / Datadog ingestion    | $0.50 per GB ingested; LLM logs add up fast       |
| GPU node IPv4 (AWS)               | $3.60/month per public IP                         |
| EKS / GKE control plane           | $73/month per cluster                             |
| DCGM / Prometheus storage         | $15-100/month                                     |

For a mid-size cluster (~$20k/month in GPUs), "hidden" infra typically adds $1500-$4000/month. Budget for it.

## 9. Worked example: chatbot at 50 RPS sustained

Assumptions:

- 50 requests/sec sustained.
- 256-token median input, 256-token median output.
- Llama-3.1-8B FP8 on H100, 7600 tok/s per GPU.

Calculations:

- Output tokens per second = 50 × 256 = 12,800 tok/s.
- GPUs required to meet steady state = ceil(12,800 / 7600) = 2 GPUs.
- Add 50% headroom for bursts and KV churn → 3 GPUs minimum, ideally 4 (one node).

Cost:

- 4× H100 on-demand: $12.29 × 4 × 730 hr/month = **$35,886/month**.
- 4× H100 3-yr reserved: $5.60 × 4 × 730 = **$16,352/month**.
- Add ALB + egress + storage + logs: ≈ $1500/month.
- **Total reserved: ~$17.9k/month** for ~130 M output tokens/day = ~3.9 B/month.
- Cost per million output tokens (blended): **~$4.60** at on-demand, **~$2.10** reserved.

Note this is higher than the per-GPU $/M token because of headroom; nobody runs at 100% utilization in production.

## 10. Comparing self-host to API providers

For Llama-3.1-class models (Q2 2026 API prices, approximate):

| Provider                                      | Input $/M | Output $/M |
| --------------------------------------------- | --------- | ---------- |
| Anthropic Claude Haiku 4.5 (comparable to 8B) | $0.80     | $4.00      |
| Together Llama-3.1-8B-Instruct                | $0.18     | $0.18      |
| Anyscale Llama-3.1-70B-Instruct               | $1.00     | $1.00      |
| Self-host 8B FP8 reserved                     | $0.04     | $0.20      |
| Self-host 70B FP8 reserved (TP=4)             | $0.28     | $1.41      |
| Self-host 405B FP8 reserved (TP=8)            | $1.05     | $5.27      |

**Break-even guidance:** self-host only beats per-token APIs when you have either (a) constant high utilization, (b) data residency / compliance requirements, or (c) custom fine-tunes you cannot host elsewhere. For sporadic traffic <10 M tokens/day, the API is cheaper end-to-end after you account for SRE time, monitoring, and on-call.

## 11. Cost calculator (pseudo-code)

The repository ships a calculator at `src/monitoring/cost_tracker.py`. The core formula:

```python
def cost_per_million_output_tokens(
    gpu_hourly_usd: float,
    measured_tokens_per_second: float,
    utilization: float = 0.6,        # realistic, not peak
) -> float:
    """Return blended cost per 1M output tokens."""
    if measured_tokens_per_second <= 0:
        raise ValueError("Throughput must be positive")
    effective_tps = measured_tokens_per_second * utilization
    seconds_per_million = 1_000_000 / effective_tps
    return gpu_hourly_usd * (seconds_per_million / 3600)
```

Plug in `gpu_hourly_usd=12.29`, `measured_tokens_per_second=7600`, `utilization=0.6` → **$0.75/M output**.

Run this for every model/precision/instance combo you are evaluating before you ship the deployment.

## 12. Optimization order (in $/M-token impact order)

1. **Right-size the model.** Llama-3.1-8B vs 70B is a 5-8x cost difference. Don't pay for 70B unless your evals demand it.
2. **Quantize to FP8** on Hopper. 1.5-2x throughput, ≤1 pp quality regression.
3. **Reserve capacity** at your steady-state baseline. 2-3x.
4. **Enable prefix caching** if traffic has stable system prompts. 1.5x throughput.
5. **Continuous batching + chunked prefill** tuned per workload. 1.3-2x.
6. **Speculative decoding** for greedy generation. 1.5-2x.
7. **Move batch traffic off the serving pool** to spot. Another 60-80% on that slice.
8. **Cache responses** for repeated prompts at the edge.
9. **Tune KV memory ceiling** (`gpu_memory_utilization`). 5-15%.
10. **Pick the right hardware generation.** H200 vs H100 for 70B is a 30-40% unit-economics win.

## 13. Related

- [GPU.md](GPU.md) — picking the right GPU
- [OPTIMIZATION.md](OPTIMIZATION.md) — making the denominator bigger
- [ARCHITECTURE.md](ARCHITECTURE.md) — KV cache math driving HBM cost
