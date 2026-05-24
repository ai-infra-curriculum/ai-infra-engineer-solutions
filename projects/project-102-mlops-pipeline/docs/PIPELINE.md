# Pipeline (DAG Anatomy)

Three DAGs make up the pipeline. They are loosely coupled via `TriggerDagRunOperator`, share state only through MinIO and MLflow, and each one is designed to be **independently re-runnable** without poisoning downstream consumers.

This document covers each stage's I/O contract, failure modes, retry policy, idempotency story, and observability. If you are diagnosing a stuck pipeline, jump to the relevant DAG's "failure modes" subsection.

---

## 1. `data_pipeline`

Defined in `dags/data_pipeline.py`. Cron: `0 2 * * *` (02:00 UTC daily). Catchup disabled.

### 1.1 Tasks

```
ingest_raw → validate_schema → check_quality → preprocess → version_with_dvc → trigger_training
```

### 1.2 Task: `ingest_raw`

| Aspect | Detail |
|--------|--------|
| Input contract | `INGEST_SOURCES` env var (comma-separated URIs). Each source must be readable with the credentials in the task's K8s SA. |
| Output contract | `s3://raw/{source}/ds={execution_date}/part-*.parquet`. Manifest at `s3://raw/{source}/ds={execution_date}/_MANIFEST.json` listing object keys, row counts, ingestion start/end timestamps, source URI, and ingestion code git SHA. |
| Failure modes | Source unreachable; partial read (network drops mid-stream); credential expiry; disk pressure on worker. |
| Retries | `retries=3`, `retry_delay=timedelta(minutes=5)`, `retry_exponential_backoff=True`. |
| Idempotency | Writes to a temp prefix `s3://raw/{source}/_tmp/{run_id}/`, then atomically renames (S3 list + copy + delete) to the final `ds=` prefix. Re-runs overwrite the destination wholesale — never partial. |
| Observability | Emits `ingestion_rows_total{source}`, `ingestion_bytes_total{source}`, `ingestion_duration_seconds{source}`. Logs row counts per file. |

**Partial-failure semantics**: if one source of three fails after exhausting retries, the task fails and downstream tasks do not run. We do **not** continue with a partial ingestion because the downstream model assumes joinable data across sources. To force a partial run during incident response, set the Airflow Variable `INGEST_ALLOW_PARTIAL=true` and the task will skip dead sources with a warning.

### 1.3 Task: `validate_schema`

| Aspect | Detail |
|--------|--------|
| Input | All `s3://raw/*/ds={execution_date}/` written by `ingest_raw`. |
| Output | Validation report at `s3://raw/_validation/ds={execution_date}/report.json`. |
| Engine | `pandera` schema declared in `src/data/validation.py::RAW_SCHEMA`. Checks column presence, dtype, nullability, and value range constraints. |
| Failure modes | Schema drift (column added/removed/renamed upstream), dtype change (string → int), null rate exceeds `MAX_NULL_RATE` (default 0.05). |
| Retries | `retries=0`. A schema failure is a *real* problem; retrying does not help. |
| Idempotency | Pure function of inputs; safe to re-run. |
| Observability | Emits `validation_pass_total{check}` / `validation_fail_total{check}`, `data_quality_score{dataset}`. |

**When this fails**, do **not** re-run the DAG until either (a) upstream is fixed, or (b) you update `RAW_SCHEMA` with an explicit migration. The validation report includes the offending rows (up to 100) for triage.

### 1.4 Task: `check_quality`

Statistical quality checks that go beyond schema: row count vs 7-day average, cardinality changes on categorical features, mean/std drift on numerics, duplicate primary key detection.

Quality is scored 0.0–1.0; a score below `MIN_QUALITY_SCORE` (0.85) fails the task. Unlike schema validation, this can legitimately recover — if `ingest_raw` ran during a partial upstream outage, the next day's run will pass. We therefore set `retries=1, retry_delay=timedelta(hours=12)` so the task naturally heals via the next ingestion cycle when scheduled with `--catchup=False`.

### 1.5 Task: `preprocess`

| Aspect | Detail |
|--------|--------|
| Input | `s3://raw/*/ds={execution_date}/`. |
| Output | `s3://features/v={FEATURE_VERSION}/ds={execution_date}/features.parquet` plus `schema.json`, `stats.json`, `MANIFEST.yaml`. |
| Engine | Pandas + scikit-learn `ColumnTransformer` declared in `src/data/preprocessing.py`. |
| Failure modes | OOM on large input (pandas is single-node); skew in categorical encoder (new category not seen during fit); date parsing edge cases. |
| Retries | `retries=2`, `retry_delay=timedelta(minutes=15)`. OOM is not solved by retry; the task runs in a K8sPodOperator with `resources.requests.memory=4Gi, limits.memory=8Gi` and we have an alert for OOMKilled. |
| Idempotency | Output path is fully determined by `(FEATURE_VERSION, execution_date)`; writes are atomic via temp-prefix rename. |
| Observability | `preprocessing_duration_seconds`, `preprocessing_rows_total`, `feature_cardinality{feature}`. |

The `ColumnTransformer` is **fit on the training partition only**, then serialized to `s3://features/v={FEATURE_VERSION}/transformer.joblib` via `joblib.dump`. Inference reuses this exact artifact to guarantee train/serve consistency. Re-fitting on every run would cause silent skew when category cardinalities drift.

### 1.6 Task: `version_with_dvc`

Calls `dvc add` on the new `s3://features/v={N}/ds={ds}/` directory, pushes the `.dvc` pointer file, and commits to a side branch `data/auto/{ds}`. See `DVC.md` for the full lifecycle. The task is fully idempotent: `dvc add` on identical content is a no-op.

### 1.7 Task: `trigger_training`

`TriggerDagRunOperator` that conditionally triggers `training_pipeline` only when:

```python
should_retrain = (
    feature_drift_score > DRIFT_THRESHOLD
    or days_since_last_training >= 7
    or Variable.get("FORCE_RETRAIN", "false") == "true"
)
```

This is the "skip if nothing changed" gate. It exists because retraining a perfectly good model every night burns compute and adds a non-zero chance of replacing a calibrated production model with a marginally different one — model churn is a real production hazard.

---

## 2. `training_pipeline`

Defined in `dags/training_pipeline.py`. Triggered by `data_pipeline` (or manually). No cron.

### 2.1 Tasks

```
load_features → train_models (TaskGroup, 4 parallel) → evaluate_models → select_champion → register_model → trigger_deployment
```

### 2.2 Task: `load_features`

| Aspect | Detail |
|--------|--------|
| Input | `dag_run.conf["features_uri"]` (passed by `data_pipeline`) or latest `s3://features/v=*/ds=*/`. |
| Output | Loads the Parquet into memory; passes the path via XCom (not the data itself — XCom is a SQLite/Postgres value, not a data bus). |
| Failure modes | Path does not exist (race with feature versioning); Parquet corruption; schema mismatch vs `schema.json`. |
| Retries | `retries=3, retry_delay=timedelta(minutes=2)`. |
| Idempotency | Read-only. |

### 2.3 TaskGroup: `train_models`

Trains four candidates **in parallel** via a dynamic task group: `logreg`, `rf`, `gbm`, `xgb`. Each one:

1. Opens an MLflow run nested under the parent training run.
2. Runs `RandomizedSearchCV` with a model-specific hyperparameter grid (`n_iter=20`, `cv=5`).
3. Logs params, metrics (per CV fold and aggregate), the best estimator as an `mlflow.sklearn` model, and an evaluation report PNG.
4. Tags the run with `dataset_hash`, `feature_version`, `code_sha`, `python_version`, `sklearn_version`.

| Aspect | Detail |
|--------|--------|
| Resource profile | `requests.cpu=2, requests.memory=4Gi` per training pod. XGBoost is the heaviest; the others fit comfortably. |
| Failure modes | Numerical instability (LogReg on poorly scaled features); CV split with all one class (rare; fixed by `stratify=y`); MLflow tracking server unreachable. |
| Retries | `retries=2, retry_delay=timedelta(minutes=5)`. The tracking-server unreachable case usually retries through. |
| Idempotency | A retry creates a *new* MLflow run, not an overwrite. This is deliberate — MLflow runs are append-only. The `select_champion` task picks the best run regardless of how many were created. |
| Observability | `model_training_duration_seconds{model}`, `model_cv_score{model,metric}`. |

**Partial-failure semantics for the TaskGroup**: if 3 of 4 models train successfully and 1 fails after retries, the DAG continues with `trigger_rule=ONE_SUCCESS` on `evaluate_models`. We do not require all 4 to succeed; the champion selection runs over whatever finished. A note is logged so the on-call engineer knows the search space was narrower than usual.

### 2.4 Task: `evaluate_models`

Pulls all child runs from the parent run, evaluates each model's logged artifact against the **same** holdout split (deterministic via fixed `random_state=42`), and writes a comparison report to MLflow as an artifact on the parent run.

The holdout is **not** the CV holdout used during training — it's a separate temporal slice (`ds` ≥ the most recent 7 days), which approximates the train-serve skew you'll see in production better than i.i.d. cross-validation.

### 2.5 Task: `select_champion`

Picks the best model by **F1 on the temporal holdout**, with two tie-breakers: prefer the model with smaller artifact size (cheaper to serve), then prefer the one with shorter training time (cheaper to retrain). Records the decision and rationale as tags on the chosen run.

If no model meets `MIN_F1_SCORE` (0.70), the task fails with `AirflowFailException` (which prevents retries — see Airflow 2.6+ behavior). The current Production model stays in place. We explicitly choose to fail rather than promote a marginal model, because a too-quiet failure here is much harder to spot than a noisy DAG-failure alert.

### 2.6 Task: `register_model`

Registers the champion run's model into the MLflow Registry as `churn-classifier` with stage `None`. The promotion to `Staging` happens in the deployment pipeline only after the smoke tests pass — registration is intentionally separate from promotion.

| Aspect | Detail |
|--------|--------|
| Idempotency | `mlflow.register_model` is not idempotent — it always creates a new version. We deduplicate by comparing the new model's run UUID to the existing latest version's `run_id` tag; if they match, we skip registration. |
| Failure modes | Registry server down; concurrent registration race (two DAGs registering the same name at once). |
| Retries | `retries=3, retry_delay=timedelta(minutes=2)`. |

### 2.7 Task: `trigger_deployment`

`TriggerDagRunOperator` for `deployment_pipeline`. Passes `dag_run.conf={"model_name": "churn-classifier", "model_version": str(new_version)}`. No conditional; if we registered a new version, we always attempt to deploy it.

---

## 3. `deployment_pipeline`

Defined in `dags/deployment_pipeline.py`. Triggered by `training_pipeline` (or manually via `scripts/promote-model.sh`).

### 3.1 Tasks

```
validate_model → deploy_to_staging → run_integration_tests → shadow_compare → promote_to_production → deploy_to_production → smoke_test → notify
```

### 3.2 Task: `validate_model`

Loads `models:/churn-classifier/{version}` and runs a synthetic-input sanity battery:

- Model accepts the documented input signature.
- Model returns probabilities in `[0, 1]`.
- Model is not constant (`np.std(predictions) > 1e-6`).
- Model size is below `MAX_MODEL_SIZE_MB` (default 100 MB) — prevents accidentally promoting a 2 GB random forest.

| Aspect | Detail |
|--------|--------|
| Failure modes | Model artifact corrupt; missing serialization dependencies; signature mismatch. |
| Retries | `retries=0`. A bad model does not get better with a retry. |
| Idempotency | Pure function of model version. |

### 3.3 Task: `deploy_to_staging`

Renders `kubernetes/predictor/deployment.yaml` (a Jinja2 template) with the new `MODEL_VERSION` env var and applies it to the `ml-staging` namespace via `KubernetesPodOperator` running `kubectl apply`. Waits for the rollout via `kubectl rollout status` with `--timeout=300s`.

The staging deployment is a single replica with the same image as production but a different `Service`. It is a real K8s rollout, not a docker-compose-style fake — staging exists to catch container-level issues (missing libs, wrong CUDA version, OOM under realistic input shape).

| Aspect | Detail |
|--------|--------|
| Failure modes | ImagePullBackOff (registry auth lost); OOMKilled (model larger than memory request); readiness probe failing (model load taking >30 s). |
| Retries | `retries=1`. K8s often heals one-shot transients on retry. |
| Idempotency | `kubectl apply` with a fully-specified manifest is idempotent. |

### 3.4 Task: `run_integration_tests`

Runs `scripts/test-pipeline.sh` against the staging Service. Sends 100 requests built from `tests/fixtures/inference_payloads.json` and asserts:

- All responses have HTTP 200.
- p99 latency < 500 ms.
- Response schema matches `tests/fixtures/inference_response_schema.json`.

| Aspect | Detail |
|--------|--------|
| Failure modes | Service not yet ready (race with K8s rollout); fixtures stale relative to new model signature. |
| Retries | `retries=2, retry_delay=timedelta(minutes=1)`. |

### 3.5 Task: `shadow_compare`

Pulls the most recent batch predictions of the **current Production** model and re-scores the same inputs with the **candidate** model. Computes agreement rate (predictions within 0.05 absolute difference) and disagreement segments.

Fails if agreement < 95% **and** the candidate's holdout F1 is not at least 2% better. The combined gate exists because a candidate that disagrees a lot but is genuinely better should still ship; a candidate that disagrees a lot and is only marginally better usually represents noise we don't want in production.

### 3.6 Task: `promote_to_production`

Transitions the Registry stage from `Staging` → `Production` and tags the previous Production version `archived_at={ts}, archived_by={dag_run.run_id}`. This is the actual cutover at the registry level — anything after this point that fails leaves Production in a known-good state because the cutover at the K8s level happens in the *next* task.

### 3.7 Task: `deploy_to_production`

Blue/green flip. The two `Deployment` resources `predictor-blue` and `predictor-green` both exist permanently. We update the inactive one to the new model version, wait for its rollout, then patch the `predictor` `Service` selector to point at it. Old color stays running for `ROLLBACK_WINDOW_MINUTES` (default 30) so we can revert with a single `kubectl patch service predictor -p '{"spec":{"selector":{"color":"<previous>"}}}'`.

| Aspect | Detail |
|--------|--------|
| Failure modes | Rollout never becomes Ready; service patch race with HPA. |
| Retries | `retries=0`. A production deployment failure requires human eyes. |
| Idempotency | The flip itself is idempotent; re-applying the same selector is a no-op. The Deployment update is also idempotent at the manifest level. |

### 3.8 Task: `smoke_test`

50 production-shaped requests against the live production Service. If any fail or latency p99 > 1000 ms, the task fails and the next task (`rollback`, not shown in the happy path) is triggered via `trigger_rule=ONE_FAILED`.

### 3.9 Task: `notify`

Posts a Slack message and updates a Grafana annotation with the new model version, F1 score, deployment time, and run URL.

---

## 4. Re-running safely

Re-runs of DAGs are common during incident response. The guarantees:

- **`data_pipeline` for a past `ds`**: safe. Outputs are partitioned by `ds`; re-running overwrites the partition atomically. Downstream training/deployment will not automatically re-trigger unless you set `FORCE_RETRAIN=true`.
- **`training_pipeline` standalone**: safe. Creates a new MLflow run and new registry version. Old versions are untouched.
- **`deployment_pipeline` standalone**: requires the operator to pass `dag_run.conf` explicitly (`{"model_name": "...", "model_version": "..."}`). If you re-run with the same version that is already Production, the deployment is a no-op at the K8s level (selector already points at it) but the registry transition is also idempotent.

### 4.1 Backfills

`airflow dags backfill data_pipeline -s 2026-04-01 -e 2026-04-30` re-runs ingestion for April. Concurrency is capped at 4 days at a time (`pool=data_pipeline_pool` with 4 slots) so we don't saturate MinIO. Backfills explicitly **do not** trigger training; the `trigger_training` task is configured to skip when `dag_run.run_type == "backfill"`.

---

## 5. Observability quick reference

When a DAG is misbehaving, check, in order:

1. **Airflow UI → DAG → Graph view**: which task is red / running too long?
2. **Task logs**: structured JSON via `src/common/logger.py`. Search by `run_id`.
3. **Prometheus**: `pipeline_duration_seconds_bucket{dag_id="..."}` for runtime regressions, `pipeline_runs_total{status="failed"}` for failure rates.
4. **Grafana → MLOps Overview**: per-DAG success rate, p95 duration, last-success age.
5. **MLflow UI**: for training DAGs, the parent run shows nested child runs with full param/metric history.

For specific failure modes, see `TROUBLESHOOTING.md`.
