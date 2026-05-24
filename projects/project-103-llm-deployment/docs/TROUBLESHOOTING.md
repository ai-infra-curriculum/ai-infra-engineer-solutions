# LLM Serving Troubleshooting Guide

Production failure modes for LLM serving with concrete symptoms, diagnosis steps, and remediation. Ordered roughly by frequency. Each entry assumes vLLM unless noted; concepts apply to TGI and TensorRT-LLM.

> Rule before anything else: **read the metrics.** The pod logs lie or arrive late. Prometheus and DCGM tell the truth.

---

## 1. CUDA Out-of-Memory at startup or first request

**Symptoms**
- Engine pod logs `torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate ... MiB.` during weight load or first prefill.
- Pod restarts in a crash loop.
- `kubectl describe pod` shows `OOMKilled` (host RAM) or the process exits with SIGABRT (HBM OOM, not OOMKilled).

**Diagnose**
1. `kubectl exec <pod> -- nvidia-smi` to confirm HBM usage at the moment of failure.
2. Check `--max-model-len`, `--max-num-seqs`, `--gpu-memory-utilization` against the memory math in [GPU.md §1](GPU.md).
3. Look for activation spikes — long-prompt prefills are the common trigger.

**Remediate**
- Lower `--gpu-memory-utilization` to 0.88 (default is 0.9).
- Lower `--max-num-seqs` (each seq reserves up to `max_model_len × KV_per_token`).
- Lower `--max-model-len` to your real 99p prompt length, not the model maximum.
- Enable `--enable-chunked-prefill` so a 32k prompt doesn't allocate full-batch activations.
- Quantize the model (FP8 or AWQ).
- If host RAM OOMKilled, raise pod memory `requests`/`limits` — vLLM pins ~20-30 GB of CPU RAM during weight load.

---

## 2. Slow first token (TTFT p95 > target)

**Symptoms**
- `vllm:time_to_first_token_seconds{quantile="0.95"}` exceeds SLO (typically >500 ms for chat).
- Users see typing dots for seconds before the answer starts.

**Diagnose**
1. Look at `vllm:num_requests_waiting`. If > 1 sustained, the engine is queueing — you're under-provisioned, not slow.
2. Check input length distribution (`vllm:request_prompt_tokens`). A jump in prompt length explodes prefill time.
3. Inspect `DCGM_FI_PROF_SM_ACTIVE`. If pinned at 100% during prefill but free during decode, prefill is the bottleneck.
4. Check prefix cache hit rate (`vllm:gpu_prefix_cache_hit_rate`). A drop means a prompt template change broke sharing.

**Remediate**
- Add replicas (scale out) — the cheapest fix.
- Enable `--enable-chunked-prefill` if not on; it prevents long prompts from monopolizing the GPU.
- Enable `--enable-prefix-caching` if traffic has stable prefixes.
- Use prefill-decode disaggregation (vLLM 0.6+ disagg or NVIDIA Dynamo) for >2k median input length.
- Shorten system prompts. A 2000-token system prompt is a tax on every request.
- If prompts are RAG-driven, reduce `top_k` or chunk size.

---

## 3. Throughput plateau (adding replicas doesn't help)

**Symptoms**
- Aggregate output tokens/sec stops growing as you add replicas.
- Individual replicas show high GPU utilization but `vllm:num_requests_running` is low.

**Diagnose**
1. Check the load balancer distribution. `kubectl top pod -n llm-platform | sort -k3` — if traffic is skewed to a subset of pods, your service is round-robin-broken or session-affinity is hurting you.
2. Check the upstream service (RAG retriever, auth service, rate limiter). Throughput at the engine cannot exceed the slowest upstream.
3. Confirm the API tier isn't serializing requests (sync code path, single-threaded uvicorn worker, etc.).
4. Confirm clients are actually streaming responses — if they `await response.text()` the entire generation, you're limited by network buffer flushes, not GPU.

**Remediate**
- Move from `ClusterIP` round-robin to least-request via Envoy/Istio.
- Run uvicorn with `--workers $(nproc)` and gunicorn-async-style workers on the API tier.
- Stream responses with SSE; don't buffer.
- If RAG is the bottleneck, scale the embedder and vector store independently.

---

## 4. NCCL hang on tensor-parallel deployments

**Symptoms**
- Engine pod loads weights, all GPUs at 100% briefly, then **everything freezes**. No log lines, no metrics updates. Pod alive, doing nothing.
- `nvidia-smi` shows all GPUs at 100% with one process pinned, no memory motion.
- `py-spy dump --pid <pid>` shows threads stuck inside `torch.distributed`.

**Diagnose**
1. `nvidia-smi topo -m` — confirm NVLink between the GPUs the worker is using (`NV*` cells, not `SYS` or `PHB`).
2. `dmesg | grep -i nccl` for NCCL transport errors.
3. Enable verbose NCCL: `NCCL_DEBUG=INFO NCCL_DEBUG_SUBSYS=ALL`, restart the pod, capture the negotiation logs.
4. Check `/dev/shm` size — `kubectl exec <pod> -- df -h /dev/shm`. If it shows 64 MiB, that's the problem.
5. Check IB / EFA health on cross-node setups: `ibstat`, `fi_info -p efa`.

**Remediate**
- Mount `/dev/shm` as a Memory `emptyDir` of at least 4 GiB (8 GiB recommended).
  ```yaml
  volumes:
    - name: shm
      emptyDir: { medium: Memory, sizeLimit: 8Gi }
  volumeMounts:
    - { name: shm, mountPath: /dev/shm }
  ```
- Set `NCCL_P2P_LEVEL=NVL` to force NVLink usage.
- For cross-node TP (avoid this!), set `NCCL_SOCKET_IFNAME` to your fast NIC name and `NCCL_IB_HCA` to the IB device.
- Restart the pod. NCCL state is not recoverable from a partial hang.
- If hangs recur after a node update, suspect a driver/CUDA mismatch — see §10.

---

## 5. KV cache eviction churn ("preemption storm")

**Symptoms**
- Log lines: `Sequence group ... was preempted by RECOMPUTE`.
- `vllm:num_preemptions_total` rate > 0.
- ITL p95 doubles, throughput stays flat.

**Diagnose**
1. `vllm:gpu_cache_usage_perc` near 1.0 sustained → KV cache is overcommitted.
2. Watch for outlier long prompts/generations evicting smaller requests.
3. Check whether speculative decoding is on with too many `num_speculative_tokens` (each draft token consumes KV blocks).

**Remediate**
- Lower `--max-num-seqs` until preemption rate drops below 0.1/s.
- Cap `max_tokens` on incoming requests at the API tier (e.g. 2048) so a single huge generation can't dominate.
- If using FP16 KV cache, switch to `--kv-cache-dtype fp8` to double effective capacity.
- Provision more replicas if the eviction rate is structural (load-driven), not pathological.
- Investigate whether a small number of clients are issuing pathologically long generations; rate-limit by output tokens, not requests.

---

## 6. Queue saturation (sustained `num_requests_waiting > 0`)

**Symptoms**
- `vllm:num_requests_waiting` floor is > 0.
- TTFT grows linearly with time during peaks.
- KEDA/HPA scaled to `maxReplicas` and still saturated.

**Diagnose**
1. Compute required tok/s = RPS × avg output tokens. Compare to (replicas × per-replica goodput).
2. Check if `maxReplicas` is set too low (the default 5 is rarely right).
3. Verify GPU node pool isn't capped — `kubectl describe nodepool gpu-h100` and look at `limits`.

**Remediate**
- Raise `maxReplicas` and node pool `limits.nvidia.com/gpu`.
- Verify capacity is actually available — submit a test pod with the GPU resource request; if it sits Pending for >5 min, the cloud is out of stock for that instance type in that AZ.
- Move read-only/batch traffic to a separate engine pool so it can't crowd live serving.
- Add request-level admission control: return 429 with `Retry-After` when queue > threshold instead of accepting unbounded backlog.

---

## 7. Model loading slow (cold start > 5 min)

**Symptoms**
- Pod stays in `Init` or `0/1 Running` for 10+ minutes.
- Init container logs show ongoing `aws s3 sync` or `huggingface_hub` download.
- HPA scale-up doesn't help because new pods can't catch peak traffic.

**Diagnose**
1. `kubectl logs <pod> -c stage-weights` for the init container progress.
2. Check storage IOPS — `iostat` on the node, or `kubectl exec` into the pod and `dd if=/weights/model-00001-of-00030.safetensors of=/dev/null bs=4M`.
3. Measure object-storage egress bandwidth; some clouds throttle a single object to ~250 MB/s.

**Remediate**
- Bake weights into the container image for stable models. Image pull is one network operation; safetensors load is another. Trade-off: image bloats by 16-140 GB.
- Use a faster storage tier:
  - AWS: FSx for Lustre with model preloaded, mounted ReadOnlyMany.
  - GCP: Filestore Premium or GCS FUSE with read-ahead.
  - Azure: Azure NetApp Files.
- Use an init container that does parallel downloads with `aria2c` or `s5cmd` — these hit 10 GB/s aggregate.
- Pre-warm by keeping `minReplicas ≥ 2` and never letting the pool scale to zero during business hours.
- Use a model cache DaemonSet that pre-stages weights to local NVMe on every GPU node.

---

## 8. FP8 numerical drift / quality regression

**Symptoms**
- Eval scores (MMLU, GSM8K, your domain eval) drop after quantizing to FP8.
- Outputs occasionally contain `NaN` or repeated tokens.
- User reports of "the model got dumber after the upgrade."

**Diagnose**
1. Confirm calibration dataset matches production traffic distribution. A model calibrated on C4 will degrade on chat or code.
2. Run the eval harness against the FP8 and BF16 versions side by side. >1 pp MMLU drop is the red line.
3. Check for outlier activations — pre-quantization SmoothQuant should be applied for activation quantization on models known to have outliers (Llama-3, Mistral).
4. Verify the FP8 scheme: E4M3 for weights and activations is the standard; mixing E5M2 in the wrong place degrades quality.

**Remediate**
- Re-calibrate with a production-like dataset (256-512 samples is usually enough). Use `llm-compressor` or `AutoFP8`.
- Switch to AWQ INT4 for sensitive workloads — wider hardware support, often as good as FP8 on quality.
- Keep weights at FP8 but KV cache at FP16 if the quality loss is localized to KV (`--kv-cache-dtype auto`).
- Gate every quantization change behind an eval suite that runs in CI.

---

## 9. GPU utilization stuck low (< 30%) despite traffic

**Symptoms**
- `DCGM_FI_DEV_GPU_UTIL` averages 20-40% during peak.
- Throughput is well below the per-GPU spec from [COST.md §3](COST.md).
- Engine is not queueing (no preemptions, low `num_requests_waiting`).

**Diagnose**
1. Are you running `--enforce-eager`? CUDA graphs disabled drops decode throughput 10-20%.
2. Is the attention backend `XFORMERS`? Switch to `FLASHINFER` (Hopper) or `FLASH_ATTN` (Ampere).
3. Is per-request `max_tokens` very small (e.g. 32) with high request rate? The engine spends most cycles in prefill overhead.
4. Check `vllm:num_requests_running` — if it's much less than `max-num-seqs`, the engine isn't getting enough concurrent work to saturate the GPU.
5. CPU bottleneck — `kubectl top pod` shows the engine pod CPU pegged. Tokenizer and request marshalling can saturate a single core; raise CPU limits.

**Remediate**
- Set `VLLM_ATTENTION_BACKEND=FLASHINFER` on Hopper.
- Remove `--enforce-eager`.
- Raise `--max-num-batched-tokens`.
- Increase API tier concurrency to push more requests at the engine.
- If `max_tokens` is structurally tiny, batch requests at the application layer or move the workload to a higher-throughput async pool.

---

## 10. CUDA driver/runtime mismatch after node upgrade

**Symptoms**
- Pod logs: `RuntimeError: CUDA error: no kernel image is available for execution on the device` or `forward compatibility was attempted on non supported HW`.
- New nodes work, old nodes fail (or vice versa).
- Suddenly broken after a `nodepool` rolling update or a GPU operator upgrade.

**Diagnose**
1. `kubectl exec <pod> -- nvidia-smi` — compare driver version on the node to `python -c "import torch; print(torch.version.cuda)"` inside the pod.
2. The forward-compatibility matrix: driver 535 supports CUDA up to 12.4. Driver 525 caps at 12.0. A PyTorch built against 12.4 on a 525-driver node will fail.

**Remediate**
- Pin GPU operator and driver version: `driver.version=550.54.15` in the GPU operator values, never `latest`.
- Roll the driver before rolling the container image, and validate with a synthetic pod (`torch.cuda.is_available()` and a small matmul) before letting traffic in.
- Use compatibility libraries (`libcuda.so.1` from the host, not bundled) — vLLM official images do this correctly.

---

## 11. Streaming responses cut off mid-generation

**Symptoms**
- Clients receive partial completions ending abruptly.
- API logs show 200 status but token count below `max_tokens`.
- Sometimes correlated with `tcp reset` upstream.

**Diagnose**
1. Check ingress / load balancer idle timeout. AWS ALB default is 60 s; long generations exceed this and get reset.
2. Check Istio sidecar `idleTimeout`.
3. Check `keep_alive` and `client_max_body_size` settings.
4. Look for OOMKilled engine pods mid-generation (preStop hook didn't fire).

**Remediate**
- Raise the LB idle timeout to at least 600 s for chat endpoints.
- Set `proxy_buffering off` in NGINX or `disable_response_buffering: true` in Envoy for SSE endpoints.
- Implement client-side retry with offset-aware resumption when the API supports it.
- For chunked content, consider WebSocket transport instead of SSE if the LB is hostile.

---

## 12. Spot interruption mid-request

**Symptoms**
- Pod terminated with `SIGTERM` mid-generation; clients see TCP reset.
- Spot interruption event in cloud audit log.
- Brief drop in capacity then auto-recovery as a new pod schedules.

**Diagnose**
1. Confirm whether the engine pool is on spot capacity (it shouldn't be for live serving). `kubectl get node <node> -o jsonpath='{.metadata.labels.karpenter\.sh/capacity-type}'`.
2. Check PDB allowed sufficient time for graceful drain.

**Remediate**
- Move live serving to on-demand or reserved (see [COST.md §6](COST.md)).
- Set `terminationGracePeriodSeconds: 600` and a `preStop` that flips readiness off + sleeps long enough for in-flight requests.
- Use the AWS Node Termination Handler (or equivalent) to convert spot warnings into graceful drains.
- Implement idempotent request IDs so clients can safely retry on disconnect.

---

## 13. Vector store latency dominates RAG p95

**Symptoms**
- RAG endpoint p95 is 800 ms+ but the LLM-only endpoint is 300 ms.
- Tracing shows >500 ms in the embedder + vector store call.
- ChromaDB pod CPU pegged.

**Diagnose**
1. Trace a request end-to-end with OTel; identify which step costs.
2. Check vector store recall metric — high `ef_search` settings trade latency for recall.
3. Check collection size; ChromaDB performance degrades past ~10M vectors per collection.

**Remediate**
- Run the embedder on GPU (single L4 is enough for many workloads).
- Migrate to Qdrant or pgvector with HNSW (`m=16`, `ef_construction=200`, `ef_search=100`). 10x latency improvement at the same recall.
- Cache embedding lookups by hashed input text — RAG queries repeat heavily.
- Cache full retrieved-context blobs by query for 30-300 seconds depending on freshness needs.

---

## 14. Memory leak / gradual RSS growth in API pods

**Symptoms**
- API pod memory grows linearly over hours and eventually OOMKills.
- No corresponding traffic increase.
- Engine pods are fine.

**Diagnose**
1. `kubectl top pod` history; look for monotonic growth.
2. Take a `py-spy dump` and `tracemalloc` snapshot at one-hour intervals; diff allocations.
3. Common culprits: tokenizer caches without bounds, accumulating per-request OpenTelemetry spans, request-body buffering, unbounded LRU caches.

**Remediate**
- Bound any LRU cache with `maxsize`.
- Set the OTel exporter to a real backend that drains; the in-memory exporter leaks.
- Restart pods on a 24-hour rolling schedule as a stopgap. Always also find the root cause.
- Pin Python `gc` to run on a deterministic threshold if you're allocating tons of small objects.

---

## 15. Prometheus / DCGM scraping misses GPU events

**Symptoms**
- Alerts on `DCGM_FI_DEV_GPU_UTIL` never fire even during incidents.
- Grafana shows stale metrics or NaN.
- DCGM exporter pod is `Running` but `up{job="dcgm"} == 0`.

**Diagnose**
1. `kubectl logs daemonset/nvidia-dcgm-exporter -n gpu-operator-resources` for scrape errors.
2. Verify the ServiceMonitor matches the exporter's labels.
3. Confirm Prometheus `scrape_interval` ≤ alert window.
4. Check NetworkPolicy isn't blocking Prometheus → DCGM port 9400.

**Remediate**
- Open the NetworkPolicy: `namespaceSelector: { matchLabels: { name: monitoring } }`.
- Set Prometheus `scrape_interval: 15s` for GPU metrics so 1-minute alerts have ≥4 samples.
- Add a synthetic alert on `up{job=~"dcgm|llm.*"} == 0` so missing metrics paging is itself an alert.

---

## Appendix: Diagnosis cheat sheet

```bash
# Pod state
kubectl get pods -n llm-platform -l app=llm-engine
kubectl describe pod <pod>
kubectl logs <pod> --tail=200
kubectl logs <pod> --previous  # crashed pod

# GPU
kubectl exec <pod> -- nvidia-smi
kubectl exec <pod> -- nvidia-smi topo -m
kubectl exec <pod> -- dcgmi diag -r 1

# Metrics (run inside a temporary debug pod with access to Prometheus)
curl -s prom:9090/api/v1/query \
  --data-urlencode 'query=vllm:num_requests_waiting'

# Network sanity
kubectl exec <pod> -- curl -s http://localhost:8000/health
kubectl exec <pod> -- ss -tnp

# Live process inspection
kubectl exec <pod> -- py-spy dump --pid 1
kubectl exec <pod> -- py-spy top --pid 1

# Trace a request end-to-end
curl -H "traceparent: 00-$(uuidgen | tr -d '-' )-$(openssl rand -hex 8)-01" \
     http://api/generate -d @prompt.json
```

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — to understand what's running
- [DEPLOYMENT.md](DEPLOYMENT.md) — for healthy-config baselines
- [OPTIMIZATION.md](OPTIMIZATION.md) — for tuning-related issues
- [GPU.md](GPU.md) — for hardware-level diagnoses
