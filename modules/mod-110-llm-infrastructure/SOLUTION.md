# SOLUTION — LLM Infrastructure

> Read this *after* you have stood up the reference LLM serving
> stack. This document explains *why* the architecture is shaped
> the way it is and how LLM serving differs from classical model
> serving in ways that matter.

## What this module is really teaching

LLM serving looks like generic model serving from a 10,000-foot
view but is fundamentally different at the engineering level:

1. **Prefill and decode are different workloads.** Prefill is
   compute-bound, decode is memory-bound. They benefit from
   different optimizations and even different hardware.
2. **KV cache dominates memory.** A 70B model's KV cache at long
   context can dwarf the model weights themselves.
3. **Throughput vs. latency is a true trade-off**, not a "more
   is more" relationship. Continuous batching trades user
   latency for total throughput.
4. **Prefix caching is the highest-impact optimization** for chat
   workloads — but produces zero benefit on unique-prompt
   workloads.

The reference solutions build a production-grade LLM gateway
that exposes these trade-offs as configurable parameters and
emits the right metrics so operators can tune them.

## Architectural decisions and *why*

### Decision 1: vLLM as the inference runtime

The reference stack uses vLLM. The reason: it has the gentlest
learning curve and the widest model coverage of the major OSS
frameworks. TensorRT-LLM is faster but harder to operate; SGLang
is more flexible but less stable. The patterns transfer.

### Decision 2: Inference gateway in front of the model

There is always a thin gateway in front of the model serving
process. The reason: the gateway handles rate limiting,
authentication, request routing, prefix-aware load balancing,
and metric collection — concerns that are inappropriate for the
inference framework itself to handle.

### Decision 3: Continuous batching, exposed to the operator

The reference vLLM configuration enables continuous batching by
default, with the batch size and queue depth surfaced as Grafana
metrics. The reason: batching is the single most important lever
for throughput, but its effect on latency is visible only with
operator-facing metrics.

### Decision 4: Prefix-aware routing implemented at the gateway

The gateway hashes the first N tokens of each request and routes
to a deterministic backend. The reason: vLLM's prefix cache
gives 3-5x throughput improvement only if the prefix is on the
same node. Without prefix-aware routing the cache hit rate is
random.

### Decision 5: KV cache memory budget as a first-class config

The reference vLLM deployment explicitly sets ``gpu_memory_
utilization`` and ``max_num_seqs`` based on the workload's
context-length distribution. The reason: the default values
assume worst-case context and leave 30-50% of GPU memory unused.

Explicit configuration lets operators tune for their actual
distribution.

### Decision 6: Streaming responses + SSE, not WebSockets

The reference exposes streaming completions over HTTP server-
sent events (SSE), not WebSockets. The reason: SSE works with
HTTP/2, plays nicely with proxies and load balancers, and uses
existing JSON-over-HTTP tooling. WebSockets require additional
infrastructure for negligible gain at the LLM use case.

### Decision 7: Speculative decoding behind a feature flag

Speculative decoding (small draft model proposing tokens for the
large model to verify) is supported but disabled by default. The
reason: speculative decoding's speedup is highly workload-
dependent (acceptance rate determines payoff). Operators can
turn it on per-model after measuring the acceptance rate on real
traffic.

## Trade-offs we deliberately accepted

### Single-model-per-replica, multi-replica fleet

The reference deploys one model per pod, not multi-model serving
within a pod (KServe ModelMesh-style). The reason: ML platform
multi-tenancy with multiple models in one process introduces
contention that's hard to debug. For the engineer-level
deployment, one model per replica is simpler and the multi-model
gains aren't justified.

### vLLM's PagedAttention defaults

We accept the default page size (16 tokens) without tuning. The
default is good across most workloads; tuning produces small
gains at the cost of significant complexity.

### English-only tokenizer assumptions

The reference assumes the tokenizer matches the model. Multi-
lingual deployments need careful tokenizer selection but that's
beyond the curriculum's scope.

## Common mistakes graders see

1. **Treating LLM serving like classical serving**: applying CPU-
   based HPA, fixed batch sizes, request-per-replica rate limits.
   None of these fit LLM workloads.
2. **Forgetting to account for KV cache**: capacity planning that
   assumes "model weights = memory needed" undersizes the
   cluster by 5-10x at long context.
3. **Random load balancing with prefix caching enabled**: you
   pay the memory cost without getting the throughput gain.
4. **No streaming**: clients block until the full response is
   ready. Unacceptable user experience for any LLM-driven UI.
5. **Single concurrent request per replica**: throws away
   continuous batching's throughput. Replicas should handle
   dozens of concurrent requests, not one.
6. **Hot-loading models at request time**: model load times are
   30-90 seconds. Always pre-load.

## When to go beyond this implementation

- Adopt **disaggregated prefill** (separate replicas for prefill
  vs decode). Useful when prefill and decode have very different
  load profiles.
- Add **request-level prioritization** so latency-sensitive
  traffic preempts background workloads.
- Move to **TensorRT-LLM** for the next 10-30% throughput when
  vLLM's flexibility is no longer needed.

## Related curriculum touchpoints

- ``performance/mod-004-transformer-optimization`` — the
  inference-side optimizations these systems use.
- ``performance/mod-006-distributed-inference`` — the multi-GPU
  scaling story.
- ``performance/mod-007-production-deployment`` — production
  deployment patterns for LLM stacks.
- ``architect/projects/project-303-llm-rag-platform`` — the
  enterprise-architecture-level companion.
