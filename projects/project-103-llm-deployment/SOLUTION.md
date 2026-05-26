# SOLUTION — LLM Deployment Platform

> Read this *after* attempting the learning-side project.

## What problem this solves

A working LLM behind a REST endpoint is the easy part. A *deployable*
LLM platform addresses things classical model serving doesn't:

1. **Memory-bound inference** — KV-cache management dominates LLM
   throughput; getting it wrong leaves 5–10x performance on the
   table.
2. **Document-grounded answers** — without retrieval, the model
   answers from training memory; with bad retrieval, it hallucinates
   confidently.
3. **GPU cost** — LLM GPU costs are large enough that "optimize
   later" means the platform doesn't survive review.
4. **Operational observability** — TTFT, tokens per request, cost
   per call are first-class signals you must surface.

## Architectural decisions and *why*

### vLLM as the inference backend (with transformers fallback)

vLLM's PagedAttention + continuous batching is the single biggest
throughput win available. The transformers fallback exists so the
project can be brought up on a laptop without a GPU for learning
purposes — *not* as a production option.

### Multi-format document ingestion behind a uniform pipeline

A real corpus has PDFs, Markdown, HTML, JSON, CSV. Each format has
its own parsing failure modes. Putting them behind a uniform
pipeline (parse → chunk → embed → index) means downstream code never
cares about the source format.

### FP16 quantization on by default; INT8 / INT4 as opt-in

FP16 is essentially free quality-wise on most modern LLMs.
INT8/INT4 quantization is a quality trade-off that needs to be
measured per-model — the platform supports it but doesn't default to
it.

### Real-time cost tracking, in USD, per call

Cost has to be a *first-class operational metric*, exported via
Prometheus alongside latency. End-of-month surprise bills are the
single most common reason LLM projects get pulled.

### Comprehensive GPU monitoring (utilization, memory, temperature,
power)

A GPU at 100% utilization but low memory bandwidth is doing
useless work. A GPU thermally throttling at full load is bottlenecked.
Multiple metrics are needed to diagnose; exporting them via the NVIDIA
DCGM exporter is the standard pattern.

### Docker + Kubernetes from day one

LLM workloads need GPU scheduling. Building the platform without
Kubernetes from the start makes the inevitable migration painful.
The Kubernetes manifests model nodeSelector / tolerations / GPU
requests correctly.

## How to read the code

Execution-order reading path:

1. `engine/` — the vLLM adapter and the transformers fallback.
2. `rag/` — ingestion pipeline, chunking strategy, vector store.
3. `api/` — request pipeline (with cost meter visible at each stage).
4. `monitoring/` — what metrics get exported.
5. `k8s/` — GPU-aware scheduling.
6. `tests/` — especially the cost-meter tests; cost bugs are the
   easiest to ship and hardest to detect.

## What's deliberately simplified

- **No retrieval reranking.** Single-stage vector retrieval; the
  two-stage (vector → reranker → LLM) pattern is in
  `architect-solutions/projects/project-303-llm-rag-platform/`.
- **No prompt-injection defenses.** Treated separately in
  `mlops-learning/projects/project-5-llmops/` and
  `security-solutions/project-3-adversarial-defense/`.
- **No per-tenant cost ceilings.** Cost is measured, not enforced.
- **No conversation-state management.** Single-shot prompts only;
  multi-turn lives in the LLM-platform architecture project.
- **No model rotation strategy.** Single served model assumed.

## Cross-references

| Topic | Where the deeper pattern lives |
|---|---|
| Full LLM-infra module (14 exercises) | `engineer-solutions/mod-110` |
| Production LLM operations | `mlops-learning/projects/project-5-llmops/` |
| LLM platform architecture | `architect-solutions/projects/project-303-llm-rag-platform/` |
| Adversarial defense framing | `security-solutions/project-3-adversarial-defense/` |
| GPU fundamentals | `performance-learning/modules/mod-001-gpu-fundamentals/` |

## Production gap checklist

- [ ] Tenant-level cost ceilings with enforcement
- [ ] Two-stage retrieval (vector + reranker)
- [ ] Prompt-injection defenses (regex + model-based)
- [ ] PII detection on retrieval corpus and on responses
- [ ] Conversation-state management with retention controls
- [ ] Hallucination monitoring tied to retrieval evidence
- [ ] Per-prompt-class request routing (cheap → expensive escalation)
- [ ] Model artifact signature verification at load

## Time budget

- **Skim**: 1 hour.
- **Deep**: 1–2 weeks — deploy to a real GPU node, ingest a real
  corpus, measure cost per call against your assumptions.
