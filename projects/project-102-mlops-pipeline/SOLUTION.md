# SOLUTION — End-to-End MLOps Pipeline

> Read this *after* attempting the learning-side project.

## What problem this solves

Project-101 shipped a model behind an API. Project-102 answers a
different question: *how do you keep that model fresh, tracked, and
deployable without a human in every step?*

Concretely, the failure modes this pipeline addresses:

1. **No record of what trained what** — six weeks later, you cannot
   reproduce the model in production.
2. **Hand-deployed models** — somebody copies a `.pkl` to a server
   and you have no idea what's running.
3. **Schedule rot** — training "runs nightly" until a node dies and
   nobody notices for a week.
4. **Data and model drift unmonitored** — the model performs well in
   evaluation, badly in production, and the gap goes undetected.

## Architectural decisions and *why*

### Airflow for orchestration (not cron, not pure Kubernetes Jobs)

Cron has no observability, no dependency model, and no retry
semantics. Pure Kubernetes Jobs are the right primitive but require
hand-rolled DAG-of-jobs orchestration. Airflow gives you DAGs,
schedules, retries, lineage, and a UI for free.

Trade-off: Airflow itself is non-trivial to operate. Managed Airflow
(MWAA, Composer, Astronomer) is the common path.

### MLflow for experiment tracking + model registry

MLflow is the de-facto open standard. Choosing a vendor-locked
tracker (W&B, Comet, vendor-specific) trades portability for
features. The reference design uses MLflow as the substrate; the
features the vendors add can be layered on if needed.

### DVC for data + model versioning

Git versions code. DVC versions the data and model artifacts those
code commits depend on. Without DVC (or an equivalent), a model
trained on "data as of last Tuesday" cannot be reproduced.

### Validation gates between training and deployment

A trained model does *not* automatically deploy. The validation
stage checks (a) the model meets a minimum quality threshold, (b)
no protected-class metric has regressed, (c) the inference shape is
backwards-compatible. Failing any of these stops deployment.

This is the most important architectural decision in the project.
Without validation gates, the rest of the pipeline is just
"automated deployment of whatever was trained" — which is *worse*
than manual deployment, not better.

### Prometheus + Grafana for pipeline observability *and* model
monitoring

Pipeline metrics (DAG duration, success rate, retry count) and
model metrics (request rate, prediction-confidence distribution,
drift) live in the same monitoring stack. Operators need both to
diagnose "the model is acting strange" — is the pipeline broken or
is the model regressed?

### Drift detection as a separate concern from prediction monitoring

Data drift and prediction drift are different signals with different
remediations. Treating them as separate alert paths matters; the
project's drift hook calls out which kind fired.

## How to read the code

Execution-order reading path:

1. Airflow DAGs — the pipeline shape.
2. MLflow integration — how runs get logged and registered.
3. DVC configuration — what data + model artifacts get versioned.
4. Validation gates — what stops a bad model from shipping.
5. Continuous-deployment job — how a registered model becomes a
   running pod.
6. Drift detection wiring.

## What's deliberately simplified

- **Single-team Airflow.** Multi-tenant Airflow (per-team isolation,
  per-team quotas) is its own problem.
- **No multi-environment promotion.** Dev/staging/prod promotion
  lives in `mod-109 exercise-10`.
- **No feature backfill safety.** New features cannot be added with
  historical coverage; covered in `mod-105 exercise-09`.
- **No human-in-the-loop approval** beyond the validation gate.
  Real promotion to production often involves a sign-off step.

## Cross-references

| Topic | Where the deeper pattern lives |
|---|---|
| Pipeline architecture deep dive | `mod-105 exercise-01` |
| Backfill safety | `mod-105 exercise-09` |
| Streaming features | `mod-105 exercise-11` |
| Model deployment strategies | `mod-106 exercise-08` |
| GitOps with ArgoCD | `mod-109 exercise-06` |
| Multi-env promotion | `mod-109 exercise-10` |
| Governance and audit | `mlops-learning/projects/project-4-governance/` |

## Production gap checklist

- [ ] Multi-environment promotion with human-approval gate at prod
- [ ] Feature backfill workflow with point-in-time correctness
- [ ] Cost attribution per pipeline run
- [ ] Failure-blast-radius limits (one bad DAG cannot consume the
      whole pool)
- [ ] Model registry promotion tied to validation evidence in audit
      log
- [ ] On-call runbooks for each predictable failure mode

## Time budget

- **Skim**: 1 hour.
- **Deep**: 1–2 weeks — bring up Airflow + MLflow + DVC locally,
  run one full cycle, intentionally introduce a quality regression,
  verify the gate catches it.
