# vLLM Tuning Benchmarks

Sample numbers from L40S (48GB) running Mistral-7B-Instruct-v0.2; 1000 requests, 32 concurrent.

| Config | Throughput (tok/s) | p50 (s) | p95 (s) | Notes |
|---|---|---|---|---|
| Baseline (defaults) | 1,840 | 0.84 | 2.10 | reference |
| + Prefix caching (long shared prompt) | 4,200 | 0.38 | 1.05 | 2.3× — RAG/agent workloads benefit most |
| + Tensor parallel = 2 (smaller share/GPU) | 2,650 | 0.62 | 1.55 | 1.4× — not worth it for 7B on L40S; better on bigger models |
| + Speculative (7B + 1.3B draft) | 3,920 | 0.45 | 1.18 | 2.1× on long completions |
| Speculative + prefix cache | 5,400 | 0.29 | 0.85 | 2.9× combined |
| Guided JSON (vs free text, same load) | 1,610 | 0.96 | 2.30 | -12% — pay for constraint, but ZERO post-hoc validation |

## Findings

- Prefix caching is the single biggest win if any non-trivial system prompt repeats.
- Speculative decoding requires draft + main models to share tokenizer; pick a smaller fine-tune of the same family.
- Tensor parallelism shines on bigger models (13B+); on 7B/L40S the overhead outweighs the gain.
- Guided decoding has a small cost but produces parseable output 100% of the time.
