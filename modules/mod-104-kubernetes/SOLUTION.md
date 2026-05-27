# SOLUTION — Kubernetes

> Read this *after* you have stood up the reference workloads on a
> real cluster. This document explains *why* the manifests are
> shaped the way they are and which Kubernetes "best practices"
> actually matter for ML workloads vs. which are tradition.

## What this module is really teaching

Kubernetes is a platform for running stateless services. ML
workloads are not always stateless. The interesting engineering
in this module lives at the seams:

- GPU node pools that have to coexist with CPU pods without each
  starving the other.
- Long-running training jobs that need preemption-resilient
  checkpointing.
- Inference services that need fast scale-up but also long-tail
  request handling.
- Multi-tenant scheduling on shared clusters.

Generic K8s tutorials never address these. The reference
solutions do.

## Architectural decisions and *why*

### Decision 1: Liveness + readiness probes pointing at *different* endpoints

Every reference Deployment uses:

- ``livenessProbe`` -> ``/health/live`` (cheap process-alive check).
- ``readinessProbe`` -> ``/health/ready`` (heavier check that
  includes downstream deps).

The reason: ``/health`` as a combined endpoint causes liveness
failures during transient dependency outages, which restarts pods
unnecessarily and cascades the outage. Split the probes; let
readiness fail loudly while liveness stays calm.

### Decision 2: ``maxSurge=1 maxUnavailable=0`` rolling-update strategy

Every Deployment in the reference uses ``maxSurge=1`` and
``maxUnavailable=0``. The reason: this is the only configuration
that guarantees zero-downtime rollouts at any replica count. The
default (``maxUnavailable=25%``) causes capacity dips during
rollout that show up as user-visible 503s.

The cost: rollouts take longer (one pod at a time). For ML
serving the latency-spike tax is worse than the rollout-duration
tax.

### Decision 3: Pod anti-affinity across nodes / zones

Inference Deployments include:

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector: {matchLabels: {app: model-api}}
          topologyKey: kubernetes.io/hostname
```

The reason: a single-node failure (or a single-zone outage)
shouldn't take down the whole service. Anti-affinity spreads
replicas across failure domains.

### Decision 4: ResourceQuotas + LimitRanges per namespace

Each tenant namespace ships with both a ``ResourceQuota`` (hard
cap on aggregate consumption) and ``LimitRange`` (default per-pod
resource limits). The reason: one team's runaway training job
should not be able to crash the cluster. Quotas prevent that.

LimitRanges fill in resource requests when pod manifests omit
them, which is critical for ML workloads where engineers
frequently forget to set memory limits.

### Decision 5: GPU node pools tainted, GPU pods tolerated

GPU nodes are tainted ``nvidia.com/gpu=true:NoSchedule``; GPU pods
add a matching toleration. The reason: a CPU-only pod scheduling
onto a GPU node wastes ~$3-10/hour of GPU capacity. Taints make
that mistake impossible.

### Decision 6: HPA on custom metrics, not just CPU

The reference HPA configurations scale on queue depth and p95
latency, not CPU. The reason: ML inference saturates the GPU
before it saturates the CPU; CPU-based HPA never fires. Metrics
from Prometheus (via the external-metrics adapter) drive scaling
decisions that match the actual bottleneck.

## Trade-offs we deliberately accepted

### Vanilla Deployments, not Argo Rollouts

The reference uses standard ``Deployment`` resources. Argo
Rollouts gives us better canary / blue-green primitives but adds
a cluster-level dependency. For the curriculum's scope, vanilla
Deployments are sufficient; Argo Rollouts shows up in the
performance / mlops tracks.

### Cilium-friendly NetworkPolicies, not service-mesh sidecars

Tenant isolation uses Kubernetes ``NetworkPolicy`` resources, not
an Istio / Linkerd service mesh. The reason: service meshes add
operational complexity that's only justified at significant
scale. NetworkPolicy + a CNI that enforces it (Cilium, Calico)
provides the same isolation guarantees for most workloads.

### IngressClass, not LoadBalancer-per-Service

External traffic enters via an Ingress controller, not via
``Service type=LoadBalancer``. The reason: one LB per Service
becomes $50-100/month per service in idle costs; one Ingress
controller fronting many services pays for itself in week one.

## Common mistakes graders see

1. **No resource requests**: pods land anywhere, evict
   unpredictably, and the cluster autoscaler can't make smart
   decisions.
2. **CPU limits set lower than requests**: throttles the pod
   constantly. Either remove the CPU limit or set it equal to the
   request.
3. **``imagePullPolicy: Always`` with mutable tags**: makes
   rollouts non-reproducible. Pin images by digest or tag.
4. **``hostPath`` volumes**: works on the dev cluster, fails in
   prod where nodes are ephemeral.
5. **No PodDisruptionBudget**: voluntary disruptions (node
   drains) take down the whole replica set.
6. **``kubectl apply -f``-only deploys, no manifest version
   control**: drift accumulates silently. Use GitOps (Argo CD,
   Flux) so the cluster state matches a git ref.

## When to go beyond this implementation

- Add **Karpenter** (or the cloud-native equivalent) for finer-
  grained node provisioning than the default cluster autoscaler.
- Adopt **KubeVirt** if you need to run VMs alongside containers
  on the same cluster (some ML workloads need it).
- Move to **Argo CD with App-of-Apps** for cluster-bootstrap
  configuration management.

## Related curriculum touchpoints

- ``engineer/mod-103-containerization`` — what these manifests
  schedule.
- ``engineer/mod-109-infrastructure-as-code`` — declarative
  cluster provisioning.
- ``performance/mod-006-distributed-inference`` — scaling
  inference workloads on Kubernetes.
- ``junior-engineer/project-02-kubernetes-serving`` — the user-
  facing application that uses these manifests.
