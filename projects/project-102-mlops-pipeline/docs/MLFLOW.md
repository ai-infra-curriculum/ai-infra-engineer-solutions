# MLflow Guide

MLflow 2.8.1 sits at the center of the pipeline: it tracks every training run, stores model binaries, and gates promotion. This document covers the conventions we follow and why — most of these emerged from watching things go wrong in earlier iterations.

---

## 1. Topology

```
┌────────────────────────┐         ┌──────────────────────┐
│  Tracking Server (×2)  │ ◄─────► │  Postgres (backend)  │
│  mlflow.server.app     │         │  database: mlflow    │
│  basic-auth enabled    │         └──────────────────────┘
└──────────┬─────────────┘
           │ s3:// (artifact root)
           ▼
   ┌──────────────────┐
   │  MinIO bucket    │
   │  s3://mlflow/    │
   └──────────────────┘
```

Configuration (see `kubernetes/mlflow/`):

```yaml
MLFLOW_BACKEND_STORE_URI: postgresql+psycopg2://mlflow:${PG_PASSWORD}@postgres-mlflow:5432/mlflow
MLFLOW_DEFAULT_ARTIFACT_ROOT: s3://mlflow/artifacts/
MLFLOW_S3_ENDPOINT_URL: http://minio:9000
MLFLOW_S3_IGNORE_TLS: "true"   # MinIO inside the cluster, plain HTTP
```

Two replicas because the Python WSGI app is single-threaded per worker and the registry UI can be slow under load. The backend store is the source of truth; either replica handles any read or write.

---

## 2. Experiment naming convention

Experiment names are **never** free-form. They follow:

```
{project}-{purpose}-{owner}
```

| Example | Purpose |
|---------|---------|
| `churn-baseline-platform` | Long-running baseline reproductions, owned by platform team |
| `churn-prod-platform` | The experiment that production training writes to |
| `churn-hpo-2026Q2-alice` | A scoped hyperparameter sweep owned by `alice` |
| `churn-debug-bob` | Ad-hoc debugging |

Rationale:

- The `{project}` prefix scopes the experiment to a single use case. We've had MLflow instances grow to 200+ experiments and the prefix is the only thing that makes the dropdown navigable.
- `{purpose}` distinguishes production runs from sandbox runs. The `prod` experiment is the only one the deployment DAG looks at.
- `{owner}` makes it obvious whose runs to ignore during a cleanup pass.

The `prod` experiment is created and managed by the platform code, never by an individual. We enforce this with an Airflow task that recreates the experiment description and tags on every DAG run:

```python
mlflow.set_experiment_tag("churn-prod-platform", "owner", "platform")
mlflow.set_experiment_tag("churn-prod-platform", "do_not_delete", "true")
```

---

## 3. Run anatomy

Every training run has the same shape. The convention is enforced by `src/training/trainer.py::train_one_model()`.

### 3.1 Parameters (`mlflow.log_param`)

Logged once at the start of the run. Two categories:

| Category | Examples |
|----------|----------|
| Model hyperparameters | `n_estimators`, `max_depth`, `learning_rate`, `C` |
| Run context | `dataset_uri`, `feature_version`, `holdout_strategy`, `cv_folds`, `random_state` |

Run context is critical for reproducibility. Two years from now when someone asks "why did this model perform so well", you need to know which exact features it saw, not just the model class.

### 3.2 Metrics (`mlflow.log_metric`)

| Metric | When logged | Notes |
|--------|-------------|-------|
| `cv_f1_fold_{0..4}` | After each CV fold | Step = fold index |
| `cv_f1_mean`, `cv_f1_std` | After all folds | Single value |
| `holdout_accuracy`, `holdout_precision`, `holdout_recall`, `holdout_f1`, `holdout_roc_auc` | After holdout eval | Single value |
| `training_duration_seconds` | At run end | Single value |
| `model_size_bytes` | At run end | After serialization |

Per-fold metrics are stepped so the MLflow UI graphs them; this catches "fold 4 is way worse than the others" patterns that single mean values hide.

### 3.3 Tags (`mlflow.set_tag`)

Tags are the metadata that makes the registry usable. Mandatory tags on every run:

| Tag | Example | Purpose |
|-----|---------|---------|
| `git_sha` | `a7b3c9d` | Reproduce the exact code that trained this model |
| `git_branch` | `main` | Distinguish prod from feature-branch experiments |
| `dataset_hash` | `sha256:8f3e...` | DVC content hash of the training features |
| `feature_version` | `3` | Which schema/transformation version |
| `python_version` | `3.11.6` | Environment reproducibility |
| `sklearn_version` | `1.3.2` | Models often serialize to a specific sklearn version |
| `xgboost_version` | `2.0.1` | Same |
| `pipeline_run_id` | `manual__2026-05-23T02:00:00` | Backlink to the Airflow run that produced it |
| `model_class` | `xgboost.XGBClassifier` | Filter the registry by family |
| `triggered_by` | `data_drift` / `scheduled` / `manual` | Why did we retrain? |

### 3.4 Artifacts (`mlflow.log_artifact`, `mlflow.{flavor}.log_model`)

Convention:

```
runs:/{run_id}/
├── model/                 # the model itself, mlflow.sklearn or mlflow.xgboost flavor
│   ├── MLmodel
│   ├── conda.yaml
│   ├── python_env.yaml
│   ├── requirements.txt
│   └── model.{pkl,json}
├── evaluation/
│   ├── confusion_matrix.png
│   ├── roc_curve.png
│   ├── pr_curve.png
│   ├── feature_importance.png
│   └── classification_report.json
├── data_profile/
│   └── profile.html       # ydata-profiling output
└── reproducibility/
    ├── requirements.lock.txt
    └── git_diff.patch     # if dirty working tree
```

The `reproducibility/` folder is essential for debugging "I can't reproduce this run locally" problems. We capture `git diff HEAD` so even uncommitted experimentation is recorded.

### 3.5 Model signature

Every logged model includes a `signature` and `input_example`:

```python
from mlflow.models.signature import infer_signature

signature = infer_signature(X_train, model.predict(X_train))
mlflow.sklearn.log_model(
    model,
    artifact_path="model",
    signature=signature,
    input_example=X_train.head(5),
    registered_model_name=None,   # registration is a separate step
)
```

Without a signature, downstream serving cannot validate inputs and silently produces garbage on schema drift. This has bitten us before.

---

## 4. Model Registry

### 4.1 Registered model

There is one registered model per use case: `churn-classifier`. It is **not** named after the model class (e.g. `xgboost-churn`) because the champion model class can change between versions. The registered model is the abstract concept ("the thing that predicts churn"); the version is the concrete artifact.

### 4.2 Stages

We use the classic four-stage workflow:

| Stage | Meaning | Who promotes |
|-------|---------|--------------|
| `None` | Just registered, untested | training DAG |
| `Staging` | Passed offline validation, deployed to staging namespace | deployment DAG, after `deploy_to_staging` succeeds |
| `Production` | Currently serving real traffic | deployment DAG, after `shadow_compare` and `smoke_test` pass |
| `Archived` | Replaced; kept for rollback or audit | deployment DAG, automatically when a new version is promoted |

A version moves through `None → Staging → Production`. When a new version reaches Production, the previous Production version is transitioned to `Archived`, **not deleted**. We keep all archived versions for 90 days (enforced by a weekly cleanup DAG, `mlflow_lifecycle`).

> **Note on MLflow ≥ 2.9**: Stages are deprecated in favor of aliases (`@champion`, `@challenger`). We use stages because this project predates 2.9 and because stages map cleanly onto our K8s namespace structure. For a new project today, prefer aliases — they are more flexible and avoid the implicit "one Production model per name" assumption.

### 4.3 Promotion gates

The deployment DAG enforces these gates before transitioning a version to `Production`:

| Gate | Check | Defined in |
|------|-------|-----------|
| Offline performance | `holdout_f1 >= MIN_F1_SCORE` (0.70) | `dags/deployment_pipeline.py::validate_model` |
| Non-regression | `holdout_f1 >= current_prod_holdout_f1 - 0.02` | `dags/deployment_pipeline.py::shadow_compare` |
| Artifact sanity | `model_size_bytes < 100 MB` and signature present | `validate_model` |
| Container readiness | Staging pod `Ready=True` within 5 min | `deploy_to_staging` |
| Integration tests | 100 requests, all 200 OK, p99 < 500 ms | `run_integration_tests` |
| Shadow agreement | ≥ 95% agreement with current Production, or F1 improvement ≥ 2% | `shadow_compare` |
| Smoke test | 50 requests against live production, all 200 OK, p99 < 1000 ms | `smoke_test` |

A version that fails any gate stays in `Staging` indefinitely until either a newer version overtakes it or an engineer manually transitions it to `Archived`.

### 4.4 Tagging strategy on registered versions

Run-level tags are copied to the registered version at registration time. Additionally, the registry-level tags include:

| Tag | Value | Set when |
|-----|-------|----------|
| `promoted_at` | ISO 8601 timestamp | Stage transition to Production |
| `promoted_by` | DAG run id or username | Stage transition |
| `promotion_reason` | `scheduled` / `manual` / `rollback` | Stage transition |
| `archived_at` | ISO 8601 timestamp | Stage transition to Archived |
| `last_known_good` | `true` / `false` | Updated by the smoke test |
| `rollback_target` | Previous Production version | After successful promotion |

The `rollback_target` tag is what `scripts/promote-model.sh --rollback` reads to determine where to revert.

### 4.5 Programmatic registry access

The pattern we use, via `src/training/registry.py`:

```python
import mlflow
from mlflow.tracking import MlflowClient

client = MlflowClient()

# Get current Production version
prod = client.get_latest_versions("churn-classifier", stages=["Production"])
if not prod:
    raise RuntimeError("No Production model — bootstrap required")
current_version = prod[0].version
current_run_id = prod[0].run_id

# Register a new version
new_version = mlflow.register_model(
    model_uri=f"runs:/{run_id}/model",
    name="churn-classifier",
    tags={"git_sha": GIT_SHA, "triggered_by": "data_drift"},
)

# Transition with archive of previous
client.transition_model_version_stage(
    name="churn-classifier",
    version=new_version.version,
    stage="Production",
    archive_existing_versions=True,   # the magic flag
)
```

`archive_existing_versions=True` is the safe default — it prevents the "two Production versions at the same time" footgun.

---

## 5. Loading models in serving code

The online predictor loads exactly once at container start, then serves from memory:

```python
import mlflow.pyfunc

MODEL_URI = f"models:/churn-classifier/Production"
model = mlflow.pyfunc.load_model(MODEL_URI)
```

The `models:/` URI resolves at load time to the latest version in the Production stage. This means a new deployment must roll the container — we do not hot-swap models inside a running process, because the version change must be auditable and observable, and a hot swap from MLflow polling is silent.

For the batch DAG, we load by **exact version** rather than by stage:

```python
MODEL_URI = f"models:/churn-classifier/{model_version}"   # version is in dag_run.conf
```

This guarantees that re-running the batch DAG for a past day uses the model that was Production *then*, not the one that is Production *now*.

---

## 6. Operational practices

### 6.1 Backups

The backend Postgres is backed up nightly via `pg_dump` to `s3://backups/mlflow/postgres/{ds}.sql.gz` with 30-day retention. The MinIO `mlflow/` bucket is replicated to a second bucket `mlflow-backup/` via MinIO's bucket replication. Either one alone is not enough — you need both the metadata and the artifacts to recover.

### 6.2 Database hygiene

MLflow's `runs`, `metrics`, `params`, `tags` tables grow without bound. We run a monthly Airflow job `mlflow_lifecycle` that:

1. Deletes runs in non-prod experiments older than 60 days.
2. Permanently deletes (`mlflow gc`) runs already marked deleted.
3. `VACUUM ANALYZE` on the four largest tables.

Before introducing this, the registry UI was taking 8 seconds to load. After: 200 ms.

### 6.3 Authentication

Basic auth via `mlflow.server.auth` is enabled. Users are stored in a Postgres table that the auth plugin manages. Default admin credentials are set via K8s secret `mlflow-admin-credentials` and rotated quarterly. Service accounts (Airflow workers, predictor pods) use per-component credentials, also stored as K8s secrets.

For an enterprise setup, replace basic auth with an OIDC proxy in front of the tracking server. The pattern is identical to what we do for the Airflow UI.

### 6.4 Common pitfalls

- **Logging the model without a signature**: silently breaks deployment validation. Always pass `signature=infer_signature(...)`.
- **Calling `mlflow.start_run()` without `nested=True` inside a TaskGroup**: clobbers the parent run. The `train_one_model()` helper enforces `nested=True`.
- **Comparing runs across experiments**: MLflow lets you do it, but the metrics may be on different test sets. Always sanity-check that `dataset_hash` matches.
- **Forgetting `archive_existing_versions=True`**: leaves two versions in Production. The serving code's `models:/.../Production` URI then resolves nondeterministically.
- **Using `mlflow.log_artifact` for large files (>1 GB)**: works but is slow because it streams through the tracking server. Use direct `boto3.upload_file` to the artifact store URI for large files, then log a tag pointing at the location.

---

## 7. Querying the registry from the CLI

A few patterns worth memorizing:

```bash
# List all versions of churn-classifier with their stages
mlflow models list -n churn-classifier

# Get the current Production version's metadata
mlflow models describe -n churn-classifier --version $(
  mlflow runs search \
    --experiment-name churn-prod-platform \
    --filter "tags.stage = 'Production'" \
    --max-results 1 --order-by 'attribute.start_time DESC' \
    --output-format json | jq -r '.[0].run_id'
)

# Download a model artifact locally for debugging
mlflow artifacts download -u models:/churn-classifier/Production -d ./local_model/

# Search runs that beat the current Production F1
mlflow runs search \
  --experiment-name churn-prod-platform \
  --filter "metrics.holdout_f1 > 0.85" \
  --order-by "metrics.holdout_f1 DESC"
```

The `mlflow` CLI is the fastest path during incident response — faster than clicking through the UI.
