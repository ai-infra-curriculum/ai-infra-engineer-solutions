# SOLUTION — Basic Model Serving System

> Read this *after* attempting the learning-side project. This is the
> entry-level project; the SOLUTION focuses on the patterns that
> matter for *learning*, not the patterns that matter for *scale*.

## What problem this solves

This project is the first end-to-end ML serving system in the
curriculum. Its purpose isn't novel architecture — it's wiring
together the *layers* a real production system needs, in a small
enough surface that you can hold all of them in your head at once:

1. **Model loading** — load once, not per request.
2. **HTTP API** — clean separation between request handling and
   model logic.
3. **Containerization** — reproducible runtime.
4. **Orchestration** — pod, service, deployment shapes.
5. **Monitoring** — metrics exposed in a way the rest of the stack
   can consume.
6. **CI/CD** — building, testing, and deploying without human
   handholding.

If you skip any of these layers, the project teaches less than it
could. Each is small enough to read in one sitting and important
enough that later projects will build on the same pattern.

## Architectural decisions and *why*

### ResNet50, not a custom model

The point isn't model novelty; it's *infrastructure*. A well-known
pretrained model means the test cases are unambiguous (is this image
of a cat classified as a cat?), and the failure modes are the
*infrastructure* failure modes you're here to learn — not modeling
failure modes.

### FastAPI with explicit Pydantic schemas

Pydantic schemas at the boundary mean that input validation is
declarative and the OpenAPI docs are correct without extra effort.
This is the production-default pattern; learning it early carries
forward to every later serving project in the curriculum.

### Model load at startup via FastAPI lifespan

Lazy-load-on-first-request looks fine until it produces a cold-start
spike under load. Lifespan moves the model load to deploy time, where
it's expected. This pattern recurs in every serving project from here.

### Multi-stage Dockerfile, non-root user

Multi-stage shrinks the image and reduces attack surface. Non-root is
a hard requirement for any production admission controller (Pod
Security Standards). Both are easier to build in from the start than
to retrofit later.

### Prometheus metrics with **labels you'll actually use**

Per-endpoint counters, per-endpoint latency histograms, model
confidence distributions. Avoid the common trap of exposing dozens
of metrics no one queries — exposing the right four metrics with the
right labels is enough.

### Kubernetes manifests as plain YAML, not Helm

For a learning project, raw YAML keeps the lesson focused on
Kubernetes itself. Helm chart authoring is its own exercise later
(`mod-104 exercise-07`).

### GitHub Actions CI: build → test → push → deploy

A pipeline this size is short enough to read in one screen. Resist
adding stages until they're justified by an actual failure mode.

## How to read the code

Execution-order reading path:

1. The Pydantic schemas — the system's contract.
2. The model wrapper — the only place ML code touches Python.
3. The FastAPI app — request flow.
4. The lifespan handler — where the model gets loaded.
5. The Dockerfile — what ships.
6. The Kubernetes manifests — what runs in the cluster.
7. The CI workflow — what happens on commit.

## What's deliberately simplified

- **No autoscaling.** Single replica or static replicas. HPA comes in
  `mod-104 exercise-06`.
- **No batching.** Single-request inference. Batching is in
  `mod-101 exercise-09`.
- **No model versioning.** One model, baked into the image. Model
  registry integration is in `mod-106 exercise-03`.
- **No traffic-splitting deploy.** Rolling update only. Canary /
  blue-green / shadow come in `mod-106 exercise-08`.
- **No authentication.** Open endpoint. Auth lives in `mod-107
  exercise-04`.

These omissions are intentional — they keep the project's surface
small enough to study end-to-end in one weekend.

## Cross-references

| Topic | Where the deeper pattern lives |
|---|---|
| Production serving (factory, lifespan, rate-limit) | `mod-101 exercise-08` |
| Batching | `mod-101 exercise-09` |
| HPA with custom metrics | `mod-104 exercise-06` |
| Helm packaging | `mod-104 exercise-07` |
| Model registry | `mod-106 exercise-03` |
| Deployment strategies | `mod-106 exercise-08` |

## Production gap checklist

If you were taking this from project to production, you would need:

- [ ] Autoscaling tied to a meaningful metric (request rate or
      latency, not CPU)
- [ ] Model versioning with registry integration
- [ ] Canary / shadow deployment strategy
- [ ] Authentication and per-tenant rate limits
- [ ] Distributed tracing (OpenTelemetry) end-to-end
- [ ] Model-artifact signature verification at startup
- [ ] PodDisruptionBudget and meaningful readiness probe

## Time budget

- **Skim**: 30 min.
- **Deep**: 1 weekend — build from scratch, deploy to a local kind
  cluster, see the Prometheus metrics light up.
