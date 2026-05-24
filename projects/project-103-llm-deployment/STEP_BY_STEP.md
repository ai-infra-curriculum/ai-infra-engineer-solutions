# STEP_BY_STEP — Project 103: LLM Deployment Platform

End-to-end walkthrough from a blank Kubernetes cluster to a production-grade LLM serving platform with RAG, observability, cost analysis, and a canary rollout. Plan for **8-16 hours** spread across at least two sessions; the long-tail items are model downloads, image builds, and load tests.

Phases:

1. [Cluster setup + GPU node pool](#phase-1--cluster-setup--gpu-node-pool)
2. [Container build + push](#phase-2--container-build--push)
3. [Helm install](#phase-3--helm-install)
4. [Smoke test](#phase-4--smoke-test)
5. [Load test + tuning](#phase-5--load-test--tuning)
6. [Observability](#phase-6--observability)
7. [Cost analysis](#phase-7--cost-analysis)
8. [Rollout: canary then production](#phase-8--rollout-canary-then-production)

Each step ends with a **validation** block that must pass before continuing. Commands assume bash, `kubectl`, `helm`, `docker`, `aws`/`gcloud`/`az`, `jq`, `curl`. If something differs on your cloud, the right answer is usually in your cloud's quickstart.

---

## Phase 1 — Cluster setup + GPU node pool

### 1.1 Decide where to run

| Option | Pros | Cons | When to pick |
|---|---|---|---|
| Local: `kind` + `kindnetd` | Free, fast iteration | No GPU passthrough on most setups | Phase 1-4 dry run only |
| Local: minikube + nvidia driver plugin | Real GPU usable | Mac/Win not supported for GPU | Single-host learning on a Linux dev box |
| AWS EKS + g5 nodes | Mature, plentiful A10G GPUs | Pricey ($1.00-$1.20/hr) | This guide's reference |
| GCP GKE + L4 / A100 nodes | Strong autoscaler | Quota approval often slow | Strong alternative |
| Azure AKS + NC-series | Good for org-aligned shops | Smaller ML ecosystem | If you live in Azure |

This guide uses **EKS + g5.2xlarge (1× NVIDIA A10G, 24 GB)**. The instructions translate to GKE/AKS with cloud-specific commands.

### 1.2 Create EKS cluster

Use eksctl for a one-shot create. Save as `cluster.yaml`:

```yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: llm-deploy
  region: us-west-2
  version: "1.29"
managedNodeGroups:
  - name: cpu
    instanceType: m6i.xlarge
    minSize: 2
    desiredCapacity: 2
    maxSize: 4
    volumeSize: 80
  - name: gpu-a10g
    instanceType: g5.2xlarge
    minSize: 0
    desiredCapacity: 1
    maxSize: 3
    volumeSize: 200
    labels:
      workload: llm
      nvidia.com/gpu: "true"
    taints:
      - key: nvidia.com/gpu
        value: "true"
        effect: NoSchedule
    iam:
      withAddonPolicies:
        autoScaler: true
        ebs: true
addons:
  - name: vpc-cni
  - name: coredns
  - name: kube-proxy
  - name: aws-ebs-csi-driver
```

```bash
eksctl create cluster -f cluster.yaml
# 15-25 minutes
aws eks update-kubeconfig --name llm-deploy --region us-west-2
kubectl get nodes
```

**Expected output**: 2 m6i + 1 g5 node. GPU node will show `nvidia.com/gpu` not yet schedulable until the device plugin is installed.

**Pitfall**: vCPU quota for g5 instances starts at 0 in new AWS accounts. Request a quota bump at https://console.aws.amazon.com/servicequotas — "Running On-Demand G and VT instances" — to at least 8 vCPU before this step.

### 1.3 Install NVIDIA GPU operator

```bash
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

kubectl create namespace gpu-operator || true
helm install --wait gpu-operator \
  -n gpu-operator \
  nvidia/gpu-operator \
  --set driver.enabled=false \
  --set toolkit.enabled=true
```

(EKS-optimized AMIs already include the driver; we only deploy the toolkit + device plugin.)

### Validation 1

```bash
# Node has the GPU resource
kubectl describe node -l workload=llm | grep -E 'nvidia.com/gpu|Allocatable' -A2

# Test pod sees the GPU
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  restartPolicy: OnFailure
  tolerations:
    - key: nvidia.com/gpu
      operator: Exists
      effect: NoSchedule
  containers:
    - name: cuda
      image: nvidia/cuda:12.4.0-base-ubuntu22.04
      command: ["nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
EOF

sleep 30
kubectl logs gpu-test            # should show the A10G
kubectl delete pod gpu-test
```

**Pass criteria**: `nvidia-smi` shows `NVIDIA A10G` with 24 GB total memory. Without it, do not proceed — every later step assumes GPU scheduling works.

---

## Phase 2 — Container build + push

### 2.1 Container registry

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-west-2
REPO=llm-api

aws ecr create-repository --repository-name $REPO --region $REGION || true
aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
```

### 2.2 Build image

The repo's `Dockerfile` is multi-stage. Inspect first:

```bash
grep -E '^FROM|^RUN|^COPY' Dockerfile | head -30
```

Build:

```bash
TAG=$(git rev-parse --short HEAD)
IMAGE=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$TAG

docker build \
  --platform linux/amd64 \
  -t $IMAGE \
  --build-arg PYTHON_VERSION=3.11 \
  --build-arg VLLM_VERSION=0.4.2 \
  .
```

Expect ~12-25 minutes for the first build (downloads torch, vllm, sentence-transformers). Subsequent builds with the layer cache: 1-3 minutes.

### 2.3 Push

```bash
docker push $IMAGE
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest
echo "Image: $IMAGE"
```

### Validation 2

```bash
aws ecr describe-images --repository-name $REPO --region $REGION \
  --query 'reverse(sort_by(imageDetails,& imagePushedAt))[0]'
```

**Pass criteria**: The image you just pushed appears with size 6-10 GB (typical for vLLM + sentence-transformers + cuda runtime). If > 15 GB, your Dockerfile is leaving build artifacts in the runtime layer — see Phase 5 tuning.

**Pitfall**: If you build on Apple Silicon and forget `--platform linux/amd64`, the image will fail to schedule on EKS x86_64 nodes with `exec format error`. Always pass the platform flag explicitly.

---

## Phase 3 — Helm install

### 3.1 Prepare values

Create `values.local.yaml`:

```yaml
image:
  repository: <ACCOUNT>.dkr.ecr.us-west-2.amazonaws.com/llm-api
  tag: <TAG>
  pullPolicy: IfNotPresent

llm:
  modelName: TinyLlama/TinyLlama-1.1B-Chat-v1.0
  modelMaxLen: 2048
  gpuMemoryUtilization: 0.85
  tensorParallelSize: 1
  dtype: float16

resources:
  requests:
    cpu: "2"
    memory: 12Gi
    nvidia.com/gpu: "1"
  limits:
    cpu: "4"
    memory: 20Gi
    nvidia.com/gpu: "1"

tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule

nodeSelector:
  workload: llm

chromadb:
  enabled: true
  persistence:
    enabled: true
    storageClass: gp3
    size: 50Gi

redis:
  enabled: true

ingress:
  enabled: true
  className: alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip

hpa:
  enabled: true
  minReplicas: 1
  maxReplicas: 4
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 60 }
```

Replace `<ACCOUNT>` and `<TAG>`.

### 3.2 Install

```bash
kubectl create namespace llm-platform || true

helm dependency update ./helm-chart      # if Chart.yaml has dependencies
helm install llm-api ./helm-chart \
  -n llm-platform \
  -f values.local.yaml \
  --wait --timeout 20m
```

The first install takes 10-20 minutes — vLLM downloads the model into a PVC.

### 3.3 Inspect

```bash
kubectl get pods -n llm-platform -w     # Ctrl-C when llm-api pod is Running
kubectl describe pod -l app=llm-api -n llm-platform | tail -30
kubectl logs -l app=llm-api -n llm-platform --tail 80
```

Look for the line:

```
INFO 05-24 ... Loading model weights took XX seconds
INFO 05-24 ... Engine started, ready for requests
```

### Validation 3

```bash
kubectl wait --for=condition=Ready pod -l app=llm-api -n llm-platform --timeout=20m

# Internal smoke
kubectl exec -n llm-platform deploy/llm-api -- \
  curl -sf http://localhost:8000/health

# External smoke via Ingress
INGRESS=$(kubectl get ing -n llm-platform llm-api -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "Ingress: $INGRESS"
curl -sf "http://$INGRESS/health"
```

**Pass criteria**: both health endpoints return 200. The ALB takes 2-5 min to provision after the ingress is created.

**Pitfalls**:

- ImagePullBackOff: the pod can't see ECR. Confirm the EKS node group's instance role has `AmazonEC2ContainerRegistryReadOnly`.
- Pending forever: GPU node is at capacity. Check `kubectl describe pod` events for `Insufficient nvidia.com/gpu` and scale node group: `eksctl scale nodegroup --cluster llm-deploy --name gpu-a10g --nodes 2`.
- OOMKilled during model load: bump memory limits or pick a smaller model.

---

## Phase 4 — Smoke test

### 4.1 Direct completion

```bash
INGRESS=$(kubectl get ing -n llm-platform llm-api -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
API_KEY=$(kubectl get secret -n llm-platform llm-api-keys -o jsonpath='{.data.primary}' | base64 -d)

curl -sS "http://$INGRESS/v1/generate" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain Kubernetes in one sentence.",
    "max_tokens": 60,
    "temperature": 0.2
  }' | jq .
```

**Expected**: a JSON envelope containing `text` (a one-sentence response), `usage.prompt_tokens`, `usage.completion_tokens`, `model`.

### 4.2 Streaming

```bash
curl -N "http://$INGRESS/v1/generate/stream" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Count from one to five.","max_tokens":40}'
```

**Expected**: SSE events stream incrementally; chunks separated by `data:` lines.

### 4.3 RAG ingest + query

```bash
curl -sS "http://$INGRESS/v1/ingest" \
  -H "Authorization: Bearer $API_KEY" \
  -F "files=@./data/sample/kubernetes-faq.md" \
  -F "collection=demo"

curl -sS "http://$INGRESS/v1/rag-generate" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"How do I get a list of pods?","collection":"demo","top_k":4}' | jq .
```

**Expected**: `answer` mentions `kubectl get pods`; `sources` array has at least one chunk from the ingested file.

### Validation 4

Run the included script:

```bash
SMOKE_INGRESS=$INGRESS SMOKE_API_KEY=$API_KEY ./scripts/smoke.sh
```

**Pass criteria**: exit code 0. Failure output names the specific check that failed.

---

## Phase 5 — Load test + tuning

### 5.1 First load test

We use `oha` (or `vegeta`, `k6`, `locust` — pick one). Install on the bastion or your laptop:

```bash
brew install oha            # macOS
# Or: docker run --rm -it ghcr.io/hatoo/oha:latest
```

Single-stream baseline:

```bash
oha -n 100 -c 1 -m POST \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Summarize the benefits of containers in two sentences.","max_tokens":80}' \
  "http://$INGRESS/v1/generate"
```

Note: P50, P95, P99, requests/s, error rate.

Concurrent:

```bash
oha -n 500 -c 10 -m POST \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Summarize the benefits of containers in two sentences.","max_tokens":80}' \
  "http://$INGRESS/v1/generate"
```

Watch in another terminal:

```bash
kubectl top pod -n llm-platform
kubectl exec -n llm-platform deploy/llm-api -- nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv -l 2
```

### 5.2 Diagnose bottlenecks

| Symptom | Likely cause | Fix |
|---|---|---|
| GPU util < 60% during the test | Single-stream or batch-1 only | Raise client concurrency; vLLM's continuous batching only kicks in with overlapping requests |
| GPU util > 90%, throughput plateaus | Genuine saturation | Scale horizontally; raise `tensorParallelSize` only if you go to multi-GPU |
| Long P99 tail | `max_num_seqs` set too low, queueing | Raise `vllm.maxNumSeqs` in values.yaml (default 128, try 256) |
| OOM kills during the test | KV cache pressure | Lower `gpuMemoryUtilization` slightly (paradoxical but leaves room for activations); lower `maxModelLen` |
| Sustained high CPU on api container | Tokenization on hot path | Bump api CPU limits to 4; consider moving tokenization into the LLM container |

### 5.3 Tuning iteration

Edit `values.local.yaml`, re-deploy, re-test:

```bash
helm upgrade llm-api ./helm-chart -n llm-platform -f values.local.yaml --wait
```

Target metrics for this exercise:

- P50 < 1 s (80-token completion)
- P95 < 3 s
- Throughput sustained > 50 tok/s/replica
- GPU utilization 70-90% under load

### Validation 5

Capture the tuned load test results:

```bash
oha -n 1000 -c 16 -m POST ... > reports/loadtest-tuned.txt
```

**Pass criteria**: meets the targets above. Document one tuning change that improved P95 by at least 20% in `reports/tuning-notes.md` — this is the deliverable for the exercise, not just hitting the number.

---

## Phase 6 — Observability

### 6.1 Install kube-prometheus-stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring || true
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --set grafana.adminPassword=admin \
  --wait
```

### 6.2 Configure the LLM API ServiceMonitor

The chart should already include a `ServiceMonitor`. Confirm:

```bash
kubectl get servicemonitor -n llm-platform
```

If missing, apply:

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: llm-api
  namespace: llm-platform
  labels:
    release: kube-prometheus
spec:
  selector:
    matchLabels:
      app: llm-api
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
EOF
```

### 6.3 GPU metrics — DCGM exporter

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/dcgm-exporter/main/dcgm-exporter.yaml
```

(Adjust namespace/labels for your setup.) The exporter runs as a DaemonSet on GPU nodes; metrics scrape automatically once the ServiceMonitor is in place.

### 6.4 Dashboards

Forward Grafana and import the dashboards from `monitoring/grafana/`:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-grafana 3000:80 &
# Open http://localhost:3000 — admin / admin
# Dashboards -> Import:
#   monitoring/grafana/llm-overview.json
#   monitoring/grafana/gpu-utilization.json
#   monitoring/grafana/cost-tracking.json
```

### 6.5 Alerts

Apply alert rules:

```bash
kubectl apply -f monitoring/prometheus/alerts.yml
```

Verify in Prometheus UI: `http://localhost:9090/alerts` (port-forward the prom service).

### Validation 6

Check that metrics flow from end to end:

```bash
# Promote one of the LLM metrics from the API
kubectl port-forward -n monitoring svc/kube-prometheus-prometheus 9090 &
sleep 3
curl -s 'http://localhost:9090/api/v1/query?query=llm_requests_total' | jq '.data.result | length'
# expect > 0

# Sample DCGM metric
curl -s 'http://localhost:9090/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL' | jq '.data.result | length'
# expect 1 per GPU
```

**Pass criteria**:

- Grafana "LLM Overview" dashboard renders with non-empty panels.
- DCGM GPU panel shows utilization climbing during a quick `oha` burst.
- At least one alert rule is in `firing` or `pending` state when you simulate an error (e.g., kill the api pod briefly).

---

## Phase 7 — Cost analysis

### 7.1 Capture cost telemetry

The chart exposes a `/v1/cost` endpoint that aggregates per-request costs from the `cost_tracker` module:

```bash
curl -s "http://$INGRESS/v1/cost" \
  -H "Authorization: Bearer $API_KEY" | jq .
```

Expected:

```json
{
  "window_hours": 24,
  "total_requests": 1487,
  "total_input_tokens": 89421,
  "total_output_tokens": 73104,
  "gpu_hours": 23.9,
  "estimated_cost_usd": {
    "gpu": 24.05,
    "tokens_marginal": 2.41,
    "total": 26.46
  },
  "recommendations": [
    "Cache hit rate is 12%; raising response cache TTL could save ~$8/day",
    "P95 prompt is 740 tokens, but median is 180 — investigate prompt template bloat"
  ]
}
```

### 7.2 Reconcile against AWS cost explorer

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -v-1d +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter '{"Dimensions": {"Key": "USAGE_TYPE_GROUP","Values":["EC2: Running Hours"]}}'
```

Build the reconciliation table:

| Source | $ / day |
|---|---|
| API `/cost` GPU estimate | 24.05 |
| AWS CE EC2 actual (g5.2xlarge × hours) | 24.40 |
| Delta | -0.35 (1.4%) |

Within 5% is healthy. Larger gaps usually mean: idle time isn't charged in the API estimate but is on the bill (cluster spinning when no traffic), or you're missing storage/egress.

### 7.3 Run the cost-optimization recommendations

For each recommendation in `/v1/cost`:

1. Apply the change in `values.local.yaml`.
2. `helm upgrade` and rerun the load test.
3. Recompute `/v1/cost` after a short steady-state window.
4. Add a row to `reports/cost-iter.md` with before/after.

Common wins:

- Response cache on identical prompts (RAG returns same chunks → identical context → identical completion if temperature=0): 10-30% cost reduction.
- Switching to AWQ-quantized weights: halves the GPU memory, lets you go from g5.2xlarge to g5.xlarge — saves ~40%.
- Spot for non-critical replicas: ~70% saving on the burst capacity.

### Validation 7

`reports/cost-iter.md` exists with at least 3 iterations, each showing the change made and the $ delta. Reconciliation table shows < 10% gap between API estimate and cloud bill.

---

## Phase 8 — Rollout: canary then production

### 8.1 Tag a new image

```bash
git checkout -b feat/new-prompt
# Make a change that affects responses, e.g., a new system prompt
NEW_TAG=$(git rev-parse --short HEAD)
NEW_IMAGE=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$NEW_TAG
docker build --platform linux/amd64 -t $NEW_IMAGE .
docker push $NEW_IMAGE
```

### 8.2 Deploy a canary

We use an Argo Rollouts style canary, with traffic split via the ALB target group weighting. If you don't run Argo, the same effect is achieved by:

- Deploying a second `Deployment` named `llm-api-canary` with `replicas: 1`.
- Pointing a `Service` named `llm-api-canary` at it.
- Configuring the ALB ingress to weight 10% to canary, 90% to stable.

Manual path:

```bash
helm install llm-api-canary ./helm-chart \
  -n llm-platform \
  -f values.local.yaml \
  --set image.tag=$NEW_TAG \
  --set nameOverride=llm-api-canary \
  --set hpa.minReplicas=1 \
  --wait

# Patch the ingress to send 10% to canary
kubectl patch ing llm-api -n llm-platform --type merge -p '{
  "metadata":{"annotations":{
    "alb.ingress.kubernetes.io/actions.weighted-routing":
      "{\"type\":\"forward\",\"forwardConfig\":{\"targetGroups\":[
         {\"serviceName\":\"llm-api\",\"servicePort\":\"80\",\"weight\":90},
         {\"serviceName\":\"llm-api-canary\",\"servicePort\":\"80\",\"weight\":10}
      ]}}"
  }}
}'
```

### 8.3 Validate canary

Generate traffic and compare metrics between `llm-api` and `llm-api-canary` pods using the Grafana dashboard's "Per Deployment" view:

- Error rate (must be <= stable + 0.5%)
- P95 latency (must be <= stable + 20%)
- Token throughput (must be >= stable - 10%)
- For quality: run the offline eval suite against both endpoints and compare scores.

Bake time: at least 30 minutes of representative traffic, or 1000 requests, whichever is greater.

### 8.4 Promote or roll back

Promote (graduated to 100%):

```bash
# Step 1: 50/50
kubectl patch ing llm-api -n llm-platform --type merge -p '{...weight 50/50...}'
sleep 600

# Step 2: 100% canary
kubectl patch ing llm-api -n llm-platform --type merge -p '{...weight 0/100...}'
sleep 300

# Step 3: switch primary, decommission canary
helm upgrade llm-api ./helm-chart -n llm-platform -f values.local.yaml --set image.tag=$NEW_TAG --wait
helm uninstall llm-api-canary -n llm-platform
# Restore default ingress routing (single target)
```

Rollback (canary failed):

```bash
kubectl patch ing llm-api -n llm-platform --type merge -p '{...weight 100/0...}'
helm uninstall llm-api-canary -n llm-platform
# File an incident note. Don't reuse the same NEW_TAG without fixing the cause.
```

### Validation 8

A successful canary record looks like:

| Time | Step | Stable err% | Canary err% | Stable p95 | Canary p95 |
|---|---|---|---|---|---|
| T+0  | 10% canary | 0.1 | 0.1 | 1.8s | 1.9s |
| T+30 | 50%        | 0.1 | 0.2 | 1.9s | 2.0s |
| T+45 | 100%       | -   | 0.2 | -    | 1.9s |

**Pass criteria**:

- No metric regression > thresholds at any step.
- Rollback rehearsal: when you're done, roll back the production tag once (replicate the rollback flow) and back, demonstrating you can move bidirectionally in under 5 minutes.

---

## Final cleanup (after the exercise)

Don't leave a g5 burning while you sleep:

```bash
# Scale GPU node group to zero
eksctl scale nodegroup --cluster llm-deploy --name gpu-a10g --nodes 0

# Or fully delete the cluster
eksctl delete cluster llm-deploy
```

ECR images: prune old tags or set a lifecycle policy.

---

## Where to go next

- Add tracing: hook OpenTelemetry into the API (see `docs/observability.md`).
- Multi-region: route based on user latency, see project-203 in senior track.
- Multi-model: add a second model in the registry and route via `?model=` query.
- LLM-as-judge eval suite: build a regression set under `eval/` and gate canaries on its score.

When something breaks, the answer is usually in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md). Don't iterate on guesses — capture the failing command's output and grep that file first.
