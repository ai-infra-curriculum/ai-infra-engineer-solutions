# Production Deployment Guide

End-to-end guide to deploying the LLM platform on Kubernetes with GPU nodes. Assumes you have an existing cluster; if not, see the "Cluster bootstrap" appendix.

## 1. Prerequisites

### 1.1 Host / driver matrix

The CUDA, driver, and container toolkit versions must match. Wrong combinations produce silent kernel launches that return zeros, or hard `CUDA_ERROR_NO_DEVICE`.

| Component                     | Validated version    | Notes                                                                 |
| ----------------------------- | -------------------- | --------------------------------------------------------------------- |
| NVIDIA Driver                 | 535.129+ (LTS) or 550.54+ (production branch) | Driver ≥535 is required for H100. 550+ unlocks FP8 perf fixes. |
| CUDA Toolkit (runtime in image) | 12.4                 | vLLM 0.6.x is built against 12.4. Do NOT mix with driver <535.        |
| cuDNN                         | 9.1                  | Bundled in PyTorch wheels — do not install host-side.                 |
| NCCL                          | 2.21+                | Required for `NCCL_P2P_LEVEL=NVL` and SHARP support on Hopper.        |
| nvidia-container-toolkit      | 1.15+                | Installed on every GPU node.                                          |
| Kubernetes                    | 1.28-1.30            | 1.31 changes DRA semantics; pin if you depend on the GPU operator.    |
| NVIDIA GPU Operator           | 24.6.x               | Manages drivers, toolkit, device plugin, MIG, DCGM exporter.          |
| Helm                          | 3.14+                |                                                                       |

Verify the host before you ever apply a workload:

```bash
ssh node-gpu-01
nvidia-smi
# Expect: driver >=535, CUDA >=12.4, GPUs listed, no Xid errors in dmesg.

nvidia-smi topo -m
# Verify NVLink (NV*) edges between GPUs you intend to use for tensor-parallel.

dmesg | grep -i 'Xid\|NVRM' | tail
# Any Xid 79 (GPU fell off the bus) or Xid 31 (memory page fault) means RMA the GPU.
```

### 1.2 NCCL sanity check

For tensor-parallel deployments, validate NCCL bandwidth before you deploy the model:

```bash
# On a single node, 8 GPUs
docker run --rm --gpus all --shm-size=1g \
  nvcr.io/nvidia/pytorch:24.06-py3 \
  bash -c "cd /opt/nccl_tests/build && ./all_reduce_perf -b 8 -e 2G -f 2 -g 8"
```

Expect ~440 GB/s busbw on H100 SXM with NVLink 4. If you see <200 GB/s, NVLink is degraded — open a ticket with the hardware vendor.

### 1.3 Storage

Model weights for 70B+ in FP16 are 140+ GB. Object storage pulls dominate startup. The deployment uses two tiers:

- **Read-only PVC** for model weights, backed by `gp3` (AWS), `pd-balanced` (GCP), or `Premium_LRS` (Azure). Mounted to all engine pods with `ReadOnlyMany` via NFS/EFS/Filestore, or per-pod via `ReadWriteOnce` with an init container that pulls from S3.
- **Local NVMe** for the KV cache scratch and request logs. Use a `local` PV or `emptyDir.medium=Memory` if you have RAM to spare.

### 1.4 IAM / secrets

- A namespaced `ServiceAccount` with the minimum permissions: read its own ConfigMap and Secret, list its own Pods (for graceful drain).
- IRSA / Workload Identity binding to access object storage for weights — **never** ship an access key inside the image.
- HuggingFace token (for gated models) stored in `Secret/llm-secrets`, mounted as `HF_TOKEN`.

## 2. Repository layout for deployment

```
project-103-llm-deployment/
├── kubernetes/
│   ├── namespace.yaml
│   ├── configmap.yaml          # non-secret env
│   ├── secret.yaml             # HF_TOKEN, API_KEYS — kustomize-templated
│   ├── pvc.yaml                # model-weights PVC
│   ├── deployment.yaml         # API + engine pods
│   ├── service.yaml            # ClusterIP + headless for engine
│   ├── hpa.yaml                # KEDA / HPA on queue depth
│   ├── gpu-node-pool.yaml      # NodePool / MIG / taint definitions
│   └── helm/                   # Helm chart wrapping the above
└── scripts/
    └── deploy.sh
```

## 3. Helm chart structure

The chart wraps the raw manifests for repeatable releases. Layout:

```
helm/llm-platform/
├── Chart.yaml                  # name, version, appVersion
├── values.yaml                 # defaults
├── values-prod.yaml            # production overrides
├── values-staging.yaml         # staging overrides
└── templates/
    ├── _helpers.tpl            # naming + label macros
    ├── serviceaccount.yaml
    ├── configmap.yaml
    ├── secret.yaml             # sealed-secrets or external-secrets
    ├── pvc.yaml
    ├── deployment-api.yaml     # CPU pods
    ├── deployment-engine.yaml  # GPU pods (one per model)
    ├── service.yaml
    ├── servicemonitor.yaml     # Prometheus Operator
    ├── pdb.yaml                # PodDisruptionBudget
    ├── hpa.yaml                # or ScaledObject for KEDA
    └── networkpolicy.yaml      # default-deny ingress except from API tier
```

`Chart.yaml`:

```yaml
apiVersion: v2
name: llm-platform
description: LLM serving platform with vLLM
type: application
version: 0.4.2
appVersion: "1.0.0"
dependencies:
  - name: kube-prometheus-stack
    version: 58.x
    repository: https://prometheus-community.github.io/helm-charts
    condition: monitoring.enabled
  - name: keda
    version: 2.14.x
    repository: https://kedacore.github.io/charts
    condition: autoscaling.keda.enabled
```

`values-prod.yaml` excerpt:

```yaml
image:
  repository: ghcr.io/your-org/llm-platform
  tag: v1.4.0
  pullPolicy: IfNotPresent

api:
  replicas: 3
  resources:
    requests: { cpu: "1", memory: "2Gi" }
    limits:   { cpu: "2", memory: "4Gi" }

engine:
  model: meta-llama/Llama-3.1-8B-Instruct
  dtype: bfloat16
  tensorParallelSize: 1
  maxModelLen: 8192
  maxNumSeqs: 256
  gpuMemoryUtilization: 0.92
  enablePrefixCaching: true
  enableChunkedPrefill: true
  replicas: 4
  resources:
    requests: { cpu: "8",  memory: "64Gi", nvidia.com/gpu: 1 }
    limits:   { cpu: "16", memory: "96Gi", nvidia.com/gpu: 1 }
  nodeSelector:
    node.kubernetes.io/instance-type: p5.48xlarge
    nvidia.com/gpu.product: NVIDIA-H100-80GB-HBM3
  tolerations:
    - key: nvidia.com/gpu
      operator: Exists
      effect: NoSchedule

autoscaling:
  keda:
    enabled: true
    minReplicas: 2
    maxReplicas: 16
    pollingInterval: 15
    cooldownPeriod: 300
    triggers:
      - type: prometheus
        metadata:
          serverAddress: http://prometheus-operated.monitoring:9090
          query: |
            avg_over_time(vllm:num_requests_waiting[1m])
          threshold: "8"

pdb:
  minAvailable: 2

monitoring:
  enabled: true
```

## 4. Engine Deployment manifest (rendered)

This is the deployment Helm produces for a single-GPU Llama-3.1-8B engine. Comments explain non-obvious choices.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-engine-llama-8b
  namespace: llm-platform
  labels: { app: llm-engine, model: llama-3-1-8b }
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      # NEVER 0 surge for GPU pods — there is rarely spare GPU capacity.
      # Set maxSurge=0 and maxUnavailable=1 to update in-place one at a time.
      maxSurge: 0
      maxUnavailable: 1
  selector:
    matchLabels: { app: llm-engine, model: llama-3-1-8b }
  template:
    metadata:
      labels: { app: llm-engine, model: llama-3-1-8b }
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        # Force scheduling onto warm-cache nodes when possible.
        cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
    spec:
      serviceAccountName: llm-engine
      terminationGracePeriodSeconds: 600   # allow long requests to drain
      priorityClassName: production-gpu
      nodeSelector:
        nvidia.com/gpu.product: NVIDIA-H100-80GB-HBM3
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      affinity:
        # Spread replicas across nodes so a single node failure cannot kill the pool.
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels: { app: llm-engine, model: llama-3-1-8b }
                topologyKey: kubernetes.io/hostname
      initContainers:
        - name: stage-weights
          image: amazon/aws-cli:2.17
          command:
            - sh
            - -c
            - |
              set -e
              if [ ! -f /weights/.complete ]; then
                aws s3 sync s3://acme-llm-weights/llama-3.1-8b-instruct/ /weights/ \
                  --only-show-errors
                touch /weights/.complete
              fi
          volumeMounts:
            - { name: weights, mountPath: /weights }
      containers:
        - name: engine
          image: ghcr.io/your-org/llm-platform:v1.4.0
          imagePullPolicy: IfNotPresent
          command: ["python", "-m", "vllm.entrypoints.openai.api_server"]
          args:
            - --model=/weights
            - --served-model-name=llama-3.1-8b-instruct
            - --dtype=bfloat16
            - --max-model-len=8192
            - --max-num-seqs=256
            - --max-num-batched-tokens=16384
            - --gpu-memory-utilization=0.92
            - --enable-prefix-caching
            - --enable-chunked-prefill
            - --disable-log-requests
            - --host=0.0.0.0
            - --port=8000
          env:
            - { name: HF_HOME, value: /weights/.hf }
            - { name: NCCL_P2P_LEVEL, value: NVL }
            - { name: NCCL_DEBUG, value: WARN }
            - { name: VLLM_ATTENTION_BACKEND, value: FLASHINFER }
            - name: HF_TOKEN
              valueFrom: { secretKeyRef: { name: llm-secrets, key: hf-token } }
          ports:
            - { name: http, containerPort: 8000 }
          readinessProbe:
            httpGet: { path: /health, port: http }
            initialDelaySeconds: 60      # weights load can take minutes
            periodSeconds: 10
            failureThreshold: 30         # be patient on cold start
          livenessProbe:
            httpGet: { path: /health, port: http }
            initialDelaySeconds: 600     # never restart during model load
            periodSeconds: 30
            failureThreshold: 5
          startupProbe:
            httpGet: { path: /health, port: http }
            periodSeconds: 10
            failureThreshold: 90         # 15 min max startup
          resources:
            requests: { cpu: "8",  memory: "64Gi", nvidia.com/gpu: 1 }
            limits:   { cpu: "16", memory: "96Gi", nvidia.com/gpu: 1 }
          volumeMounts:
            - { name: weights, mountPath: /weights }
            - { name: shm, mountPath: /dev/shm }
          lifecycle:
            preStop:
              exec:
                # Mark unready, wait for in-flight requests to finish.
                command: ["sh", "-c", "curl -s -X POST localhost:8000/shutdown; sleep 30"]
      volumes:
        - name: weights
          persistentVolumeClaim: { claimName: model-weights-llama-8b }
        - name: shm
          emptyDir: { medium: Memory, sizeLimit: 8Gi }
```

Key choices:

- `maxSurge: 0` because the cluster rarely has a spare H100 for a parallel new pod.
- `terminationGracePeriodSeconds: 600` and a `preStop` curl let the engine drain — streaming completions can run >2 minutes.
- `livenessProbe.initialDelaySeconds: 600` — do not kill a pod that is still loading 16 GB of weights.
- `/dev/shm` is bumped to 8 GiB because NCCL and inter-process communication in vLLM uses shared memory; the 64 MiB Kubernetes default causes silent corruption on tensor-parallel setups.
- `priorityClassName: production-gpu` gives serving pods preemption rights over batch/training pods.

## 5. PodDisruptionBudget

Spot interruptions on cloud GPUs are routine. A PDB prevents the cluster autoscaler and node-drain from taking down the entire pool simultaneously.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: llm-engine-llama-8b
  namespace: llm-platform
spec:
  minAvailable: 2
  selector:
    matchLabels: { app: llm-engine, model: llama-3-1-8b }
```

For spot-heavy pools, prefer `maxUnavailable: 1` with a `priorityClass` so a critical eviction can still proceed when the pool is at minimum.

## 6. HorizontalPodAutoscaler / KEDA

CPU/memory HPA is useless for LLM engines — GPUs sit at >90% util before the box is overloaded. Scale on **queue depth**, the only metric that correlates with real user latency.

Using the KEDA `ScaledObject`:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: llm-engine-llama-8b
  namespace: llm-platform
spec:
  scaleTargetRef:
    name: llm-engine-llama-8b
  pollingInterval: 15
  cooldownPeriod: 300            # avoid flapping; weights load is expensive
  minReplicaCount: 2
  maxReplicaCount: 16
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          policies:
            - type: Pods
              value: 2
              periodSeconds: 60
        scaleDown:
          stabilizationWindowSeconds: 600
          policies:
            - type: Pods
              value: 1
              periodSeconds: 120
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus-operated.monitoring:9090
        threshold: "8"
        query: |
          avg by (deployment) (
            avg_over_time(vllm:num_requests_waiting{deployment="llm-engine-llama-8b"}[1m])
          )
```

`vllm:num_requests_waiting` is exposed by vLLM directly. Target a queue depth ≈ `max_num_seqs / 4` to leave headroom for bursts.

## 7. GPU node pool

GPU nodes are special: scarce, expensive, and require taints to repel other workloads. Example (EKS Karpenter `NodePool`):

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: gpu-h100
spec:
  template:
    metadata:
      labels:
        nvidia.com/gpu.product: NVIDIA-H100-80GB-HBM3
        workload: llm-serving
    spec:
      taints:
        - key: nvidia.com/gpu
          effect: NoSchedule
      requirements:
        - key: node.kubernetes.io/instance-type
          operator: In
          values: [p5.48xlarge, p5.24xlarge]
        - key: karpenter.sh/capacity-type
          operator: In
          values: [on-demand]      # serving pool — no spot
        - key: topology.kubernetes.io/zone
          operator: In
          values: [us-east-1a, us-east-1b]
      expireAfter: 720h
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 30m
  limits:
    nvidia.com/gpu: 64
```

A parallel `NodePool` for batch workloads uses `capacity-type: spot` and a different taint (`workload=batch`). Serving pods cannot tolerate that taint, preventing accidental scheduling on preemptible capacity.

For GKE, the equivalent is a `nodepool` with `acceleratorType=nvidia-h100-80gb`, `spot=false`, and `gpu-driver-version=latest`. For Azure, AKS GPU node pools with `--node-vm-size=Standard_ND96isr_H100_v5`.

## 8. NetworkPolicy (default-deny)

Engines should only be reachable from the API tier and the Prometheus scraper.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: llm-engine
  namespace: llm-platform
spec:
  podSelector:
    matchLabels: { app: llm-engine }
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector: { matchLabels: { app: llm-api } }
        - namespaceSelector: { matchLabels: { name: monitoring } }
      ports:
        - { protocol: TCP, port: 8000 }
```

## 9. Rollout procedure

```bash
# 1. Build and push image with the new model or vLLM bump.
docker buildx build --platform linux/amd64 -t ghcr.io/your-org/llm-platform:v1.4.0 --push .

# 2. Stage in non-prod cluster, run the smoke suite.
helm upgrade --install llm-platform helm/llm-platform \
  -n llm-platform --create-namespace \
  -f helm/llm-platform/values-staging.yaml \
  --set image.tag=v1.4.0 \
  --wait --timeout 30m

scripts/smoke_test.sh https://llm-staging.example.com

# 3. Promote to prod: canary 10% via Argo Rollouts or a second Deployment + weighted Service.
helm upgrade llm-platform helm/llm-platform \
  -n llm-platform \
  -f helm/llm-platform/values-prod.yaml \
  --set image.tag=v1.4.0 \
  --set engine.canary.weight=10

# 4. Watch SLOs for 30 minutes (p95 TTFT, error rate, queue depth).
# 5. Promote to 100% or roll back.
helm rollback llm-platform <previous-revision>
```

## 10. Cluster bootstrap appendix

If you do not have a cluster yet:

```bash
# AWS — EKS with Karpenter, GPU operator
eksctl create cluster --name llm-prod --version 1.30 \
  --region us-east-1 --without-nodegroup
eksctl utils associate-iam-oidc-provider --cluster llm-prod --approve

helm install gpu-operator nvidia/gpu-operator \
  -n gpu-operator --create-namespace \
  --version v24.6.1 \
  --set driver.version=550.54.15 \
  --set toolkit.version=v1.16.1-ubuntu20.04 \
  --set dcgmExporter.enabled=true \
  --set mig.strategy=single

helm install karpenter oci://public.ecr.aws/karpenter/karpenter \
  -n karpenter --create-namespace --version 1.0.x \
  --set settings.clusterName=llm-prod
```

Then apply the `NodePool`, `Deployment`, `Service`, `PDB`, and `ScaledObject` shown above.

## 11. Smoke and rollback checklist

Before marking a deployment healthy:

- [ ] `kubectl get pods -n llm-platform` — all `Running`, restart count 0
- [ ] `/health` returns 200 from a pod-exec curl
- [ ] One end-to-end completion via the public endpoint, TTFT <1 s
- [ ] `vllm:num_requests_waiting` < 1 at steady state
- [ ] `DCGM_FI_DEV_GPU_UTIL` rises under synthetic load
- [ ] No `Xid` errors in `kubectl logs` or `dmesg` on any GPU node
- [ ] Prometheus is scraping the new pods (`up{job=~"llm.*"} == 1`)
- [ ] Grafana dashboards reflect traffic
- [ ] Alerts fire on a forced failure (kill a pod manually)

Rollback in <5 minutes is `helm rollback llm-platform <rev>`. Rehearse it.

## 12. Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — why the system looks like this
- [OPTIMIZATION.md](OPTIMIZATION.md) — how to tune the engine flags above
- [GPU.md](GPU.md) — choosing instance types
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — production failure modes
