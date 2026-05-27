# SOLUTION — MLOps

> Read this *after* you have built the MLflow + model registry +
> serving reference implementations. This document explains *why*
> the MLOps stack is shaped the way it is and which integrations
> matter at what scale.

## What this module is really teaching

MLOps is at its core a **configuration management problem
disguised as a data problem**. The reference solutions push three
ideas:

1. **Everything is versioned**: code, data, models, configuration,
   feature transformations. If any link is unversioned, you can't
   reproduce a result and you can't roll back a regression.
2. **The model registry is the source of truth, not the
   experiment tracker.** Experiments are the lab; the registry is
   production.
3. **Serving and training need a shared feature contract** or
   you'll have train-serve skew you can't diagnose.

## Architectural decisions and *why*

### Decision 1: MLflow for experiments, registry-side for production

The reference solutions use MLflow for experiment tracking *and*
the model registry. Experiments are cheap to log (every run goes
to MLflow); promotion to the registry is gated by an explicit
human or automated review.

The reason: every run logged to the registry pollutes it.
Treating "experiment" and "registered model" as distinct gives
you a clean production catalog.

### Decision 2: Data versioning via DVC + content-hashed paths

Datasets are versioned via DVC, but the underlying storage uses
content-hashed paths (e.g. ``s3://datasets/sha256/abc.../...``).
The reason: content addressing means deduplication is automatic
and stale references can be detected (the file is or isn't at the
hash; no ambiguity).

DVC adds the convenient git-aware UX on top.

### Decision 3: Model serving framework selection by workload

The reference solutions show three serving frameworks for three
workloads:

- **TorchServe**: classical models with PyTorch, batched
  inference, no LLM streaming.
- **vLLM**: LLM-shaped workloads needing continuous batching +
  KV-cache management.
- **BentoML**: heterogeneous workloads where the model is one
  part of a larger pipeline.

Picking the wrong serving stack costs 3-10x in throughput. The
reference makes the framework selection criteria explicit so the
choice is deliberate.

### Decision 4: CI/CD for models, not just code

The reference CD pipeline treats *models* as first-class
artifacts:

1. New model version registered.
2. Automated evaluation against a held-out test set.
3. Shadow deployment (real traffic, mirrored predictions).
4. Canary deployment with quality + latency gates.
5. Promotion to Production (or rollback).

Pure code-CI/CD without this is "we deploy a binary"; ML CI/CD
adds "and the binary works on real data."

### Decision 5: Feature store as the contract layer

Features used in training and features used at inference go
through the same feature-store client. The reason: train-serve
skew is the #1 silent failure mode in ML production. A single
codebase for feature computation eliminates it by construction.

For workloads not yet on a feature store, the reference uses a
shared transformation library that both training and serving
import. Same idea, smaller scale.

## Trade-offs we deliberately accepted

### MLflow over Weights & Biases / Neptune

MLflow is OSS and self-hostable; W&B / Neptune have richer UIs
but are SaaS-first. For curriculum purposes MLflow is the right
trade-off; production teams sometimes go the other way.

### Single-cloud MLflow backend

The reference deploys MLflow with PostgreSQL + S3 (or equivalent).
Multi-cloud MLflow deployments are possible but add a complexity
layer that's only justified at significant scale.

### Model formats: keep PyTorch / SavedModel; convert at the edge

We don't try to standardize on ONNX or TorchScript inside the
training stack. Conversion happens at the serving boundary if
needed. The reason: forcing a model-format conversion during
training breaks debugging and reduces what your data scientists
can experiment with.

## Common mistakes graders see

1. **Tracking experiments locally, not centrally**: nobody else
   can reproduce or compare. Always log to a shared MLflow.
2. **Untracked manual changes to registered models**: rename a
   model in the registry without recording it and downstream
   consumers break with no audit trail.
3. **Same prefix for experiment + registry artifacts**: data
   science churn pollutes the production registry.
4. **No production-stage gating**: the latest model is
   automatically deployed. Always require explicit promotion.
5. **Missing model card**: 6 months later, nobody remembers what
   data the model was trained on, what its known biases are, or
   when it should not be used.
6. **Inference doesn't read the same features as training**:
   classic train-serve skew. Fix by sharing the feature client.

## When to go beyond this implementation

- Add **continuous training** triggers (data freshness, drift
  detection) on top of the manual retrain flow.
- Adopt a **proper feature store** (Feast / Tecton) when the
  training-serving feature contract becomes a recurring source of
  bugs.
- Move to **multi-model serving** (BentoML Yatai, KServe
  ModelMesh) when you have 50+ models in production.

## Related curriculum touchpoints

- ``engineer/mod-105-data-pipelines`` — the data side of MLOps.
- ``engineer/mod-108-monitoring-observability`` — observability
  for production models.
- ``mlops/projects/project-1-ml-pipeline`` — the user-facing
  MLOps project these solutions support.
- ``ml-platform/mod-006-model-management`` — the platform-level
  view of model lifecycle.
