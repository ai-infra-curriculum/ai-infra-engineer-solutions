# Troubleshooting

Twelve failure modes that have actually happened on this pipeline (or in projects shaped like it), ordered roughly by frequency. Each one has a **symptom** section (what you see first), a **diagnosis** section (how to confirm it's this failure and not another), and a **remediation** section (how to fix it without making things worse).

For general operational orientation, see `PIPELINE.md` and `DEPLOYMENT.md`. For component-specific operations (MLflow registry, DVC GC), see those docs.

---

## 1. Schema drift in raw ingestion

### Symptom

`data_pipeline` DAG fails at the `validate_schema` task. The task log shows:

```
pandera.errors.SchemaError: column 'monthly_charges' not in dataframe.
Available columns: ['customer_id', 'tenure', 'monthly_charge', 'total_charges', ...]
```

`data_quality_score{dataset="raw"}` drops to 0 in Grafana. Slack receives the failure alert. No downstream DAGs run.

### Diagnosis

The schema validator declared `monthly_charges` (plural), and the new ingestion has `monthly_charge` (singular). To confirm this is upstream drift and not your code:

```bash
# Compare today's columns to yesterday's
aws s3 cp s3://raw/_validation/ds=2026-05-22/report.json - --endpoint-url $S3_ENDPOINT | jq '.columns'
aws s3 cp s3://raw/_validation/ds=2026-05-23/report.json - --endpoint-url $S3_ENDPOINT | jq '.columns'
```

If the column set differs and you didn't ship a schema change, it's upstream. Contact the data producer. If the rename was announced in advance and you missed it, that's a process gap to fix separately.

### Remediation

1. **Do not blindly retry the DAG.** A retry with stale code will fail identically and burn the on-call's patience.
2. Decide whether to revert upstream or adapt. Usually you adapt.
3. Update `src/data/validation.py::RAW_SCHEMA` to accept both column names during a transition window:
   ```python
   schema = pa.DataFrameSchema({
       "monthly_charge": pa.Column(float, nullable=True, required=False),
       "monthly_charges": pa.Column(float, nullable=True, required=False),
   })
   ```
   …and add a normalization step in `preprocessing.py` that maps both to the canonical name.
4. Commit the change, deploy a new Airflow worker image, then `airflow dags clear data_pipeline -s 2026-05-23` to re-run today's failed run with the new code.
5. After the transition window (typically 14 days), drop the old name.

**Prevention**: subscribe to the upstream team's schema-change channel. The cost of a one-day adaptation is much lower than a week of running on stale data.

---

## 2. Feature freshness lag

### Symptom

The model is in Production and serving traffic, but Grafana shows `feature_freshness_hours > 48` for one or more features. Predictions are subtly worse — `model_accuracy_online` has drifted down 3% over a week.

### Diagnosis

```bash
# When did each feature's source partition last update?
mc ls --recursive minio/features/v=3/ | awk '{print $NF}' | sort -u | tail -20
```

Compare to `ds={today}`. If the most recent partition is several days old, the data pipeline is silently producing empty or stale output even though the DAG shows green.

Check the upstream-source manifests:

```bash
mc cat minio/raw/crm/ds=2026-05-23/_MANIFEST.json | jq '.row_count, .source_uri'
```

If `row_count` is suspiciously low (e.g. <10% of typical), `ingest_raw` succeeded but pulled stale or partial upstream data — which the schema validator does not catch because the schema is still correct, just empty.

### Remediation

1. Add a row-count sanity check to `check_quality`:
   ```python
   if today_rows < 0.5 * trailing_7d_avg_rows:
       raise AirflowFailException(f"Row count {today_rows} is <50% of 7d avg {trailing_7d_avg_rows}")
   ```
2. Re-ingest from upstream once they confirm the issue is resolved.
3. Force-retrain only after the feature store has a full week of healthy data, otherwise the model learns from the anomalous period:
   ```bash
   airflow variables set FORCE_RETRAIN true
   airflow dags trigger data_pipeline
   ```

**Prevention**: the row-count check above plus a `feature_freshness` Prometheus gauge with an alert at >24 h. The pipeline going green does not mean the data is fresh — only that the code didn't throw.

---

## 3. MLflow tracking server unreachable

### Symptom

Training tasks fail with:

```
mlflow.exceptions.MlflowException: API request to http://mlflow.mlops-system:5000/api/2.0/mlflow/runs/create failed with exception ConnectionError
```

`model_training_duration_seconds` has no recent samples. The MLflow UI returns 502 Bad Gateway.

### Diagnosis

```bash
# Are the pods running?
kubectl -n mlops-system get pods -l app=mlflow

# Are they Ready?
kubectl -n mlops-system describe pod -l app=mlflow | grep -A 5 "Conditions:"

# What do the logs say?
kubectl -n mlops-system logs -l app=mlflow --tail=200

# Can the backend Postgres be reached from the pod?
kubectl -n mlops-system exec deploy/mlflow -- python -c "
import psycopg2; psycopg2.connect('$MLFLOW_BACKEND_STORE_URI').close(); print('ok')
"
```

Common causes, in order of frequency:
- Postgres restart caused a connection storm; MLflow pods are in CrashLoopBackoff retrying.
- Backend store URI secret was rotated but pods weren't restarted.
- MinIO is down and MLflow is blocking on artifact-server health checks.
- Network policy was tightened and is now blocking the MLflow → Postgres path.

### Remediation

For Postgres restart cause:

```bash
kubectl -n mlops-system rollout restart deploy/mlflow
kubectl -n mlops-system rollout status deploy/mlflow --timeout=120s
```

For secret rotation: same as above (pods read secrets at startup; you need a restart).

For MinIO down: fix MinIO first (see §6), then MLflow. Do not increase MLflow's startup tolerance to mask MinIO outages — that hides the real problem.

For network policy: `kubectl -n mlops-system describe networkpolicy` and verify the allow rule for MLflow → Postgres on port 5432 exists.

**Failed training runs are recoverable**: Airflow retries the task; if the retry succeeds, the run lands in MLflow. If you exhausted retries, `airflow dags clear training_pipeline -s {failed_ds}` re-runs the whole DAG, which re-trains and produces a new MLflow run. No data is lost because nothing was committed.

---

## 4. Model registry promotion blocked

### Symptom

A new model registered fine, but the deployment DAG fails at `promote_to_production` with:

```
RestException: RESOURCE_DOES_NOT_EXIST: Model version 12 not found in stage 'Staging'.
```

Or, less obviously, the DAG succeeds but `models:/churn-classifier/Production` still resolves to the *old* version.

### Diagnosis

```bash
mlflow models list -n churn-classifier
mlflow models describe -n churn-classifier --version 12
```

Possible causes:
- Version 12 was registered but never transitioned to `Staging` because `deploy_to_staging` skipped (e.g. a manual run with `dag_run.conf.skip_staging=true`).
- Two concurrent training DAGs each registered a version; the deployment DAG promoted version 11 but you're looking at version 12.
- An MLflow 2.9+ alias and a stage are both set, and the serving code is reading the alias while you're checking the stage.

### Remediation

1. Confirm the version's current stage explicitly:
   ```bash
   mlflow models describe -n churn-classifier --version 12 | jq '.current_stage'
   ```
2. If `None`, transition manually:
   ```bash
   mlflow models transition-stage -n churn-classifier --version 12 \
     --stage Staging --archive-existing-versions=false
   ```
3. Then re-run the deployment DAG from `deploy_to_staging`:
   ```bash
   airflow tasks run deployment_pipeline deploy_to_staging {run_id}
   ```

For the concurrent-registration case: prevent it by setting `max_active_runs=1` on `training_pipeline` (already configured in `dags/training_pipeline.py`). If it happened anyway because of a manual `trigger_dag`, archive the orphan version manually.

For the alias-vs-stage confusion: pick one. On this project we use stages exclusively. If you've started using aliases, audit serving code and pick a single source of truth.

---

## 5. Model loading mismatch in serving

### Symptom

The predictor pod starts but the `readiness` probe fails. Logs show:

```
AttributeError: Can't get attribute 'XGBClassifier' on <module 'xgboost' from '/usr/lib/python3.11/...'>
```

Or:

```
sklearn.exceptions.NotFittedError: This LabelEncoder instance is not fitted yet.
```

### Diagnosis

The model was trained with one library version and is being loaded with another. Check the model's `requirements.txt` artifact:

```bash
mlflow artifacts download -u models:/churn-classifier/Production/requirements.txt -d /tmp/
cat /tmp/requirements.txt
```

Compare to the predictor image's installed versions:

```bash
kubectl -n ml-serving exec deploy/predictor-blue -- pip freeze | grep -E "(scikit-learn|xgboost|numpy)"
```

If `xgboost==2.0.1` in the model artifact and `xgboost==1.7.5` in the container, that's your mismatch.

### Remediation

Either rebuild the predictor image with matching versions (preferred):

```dockerfile
# docker/predictor/Dockerfile
COPY --from=mlflow_model /model/requirements.txt /tmp/model-reqs.txt
RUN pip install -r /tmp/model-reqs.txt
```

…or pin the training environment to match the predictor image (only if you cannot rebuild). Set `MIN_VERSION_COMPAT` in CI to assert at training time:

```python
import xgboost
assert xgboost.__version__ == REQUIRED_XGBOOST_VERSION, "Train/serve version mismatch"
```

**Prevention**: the deployment DAG's `validate_model` task should diff the model's `requirements.txt` against the predictor image manifest before allowing promotion. We added this gate after the first incident; it's caught two near-misses since.

---

## 6. MinIO out of space

### Symptom

Random tasks across all DAGs fail with:

```
botocore.exceptions.ClientError: An error occurred (XMinioStorageFull) when calling the PutObject operation
```

Or MinIO becomes read-only, breaking new uploads while still serving reads.

### Diagnosis

```bash
mc admin info minio
mc du minio                    # per-bucket usage
mc du --recursive minio/mlflow # what's the biggest under mlflow/?
```

Common culprits, in our experience:
- `mlflow/` bloated by HPO sweeps logging 200 models × 20 runs each.
- `dvc-cache/` accumulated 1 TB+ because nobody scheduled `dvc gc`.
- `predictions/` retained months of batch outputs because the lifecycle policy was wrong.

### Remediation

Short-term:
1. Identify the bloated bucket and delete what you don't need:
   ```bash
   # Delete MLflow runs from a sandbox experiment older than 30 days
   mlflow experiments delete -n churn-debug-bob   # marks as deleted
   mlflow gc                                       # actually frees space
   ```
2. Run `dvc gc` as documented in `DVC.md` §6.
3. Apply or fix the lifecycle policy:
   ```bash
   mc ilm import minio/predictions < kubernetes/minio/lifecycle/predictions.json
   ```

Long-term:
- Set a per-bucket quota: `mc admin bucket quota minio/dvc-cache --hard 1TiB`.
- Alert at 80% via Prometheus on `minio_bucket_usage_object_total`.
- Move cold MLflow runs to S3 Glacier-equivalent tier (MinIO supports tiering to remote backends).

**Do not** scale the storage pool as the first response. It buys time but the root cause (missing lifecycle, missing GC) will refill any size you give it.

---

## 7. Airflow task timeouts

### Symptom

`train_models.xgb` task gets `AirflowTaskTimeout` after 60 minutes. Other models in the same TaskGroup completed in 5 minutes each.

### Diagnosis

```bash
# Was the pod killed?
kubectl -n airflow get events --field-selector involvedObject.name=<pod-name>

# Check pod resource usage right before death
kubectl -n airflow top pod <pod-name> --containers
```

If the pod was OOMKilled, you'll see `Reason: OOMKilled` and the task hit the memory limit (8 GiB by default). XGBoost's memory footprint with `tree_method=hist` on wide data can balloon if cardinality of one-hot columns explodes after upstream changes.

If not OOM but stuck CPU-bound: HPO with `n_iter=20` and `cv=5` is 100 fits; a typo in the hyperparameter grid (`n_estimators: [10000, 20000]`) silently makes each fit 100× more expensive.

If neither: the task may be deadlocked on an MLflow API call (rare but possible during tracking server saturation).

### Remediation

For OOM:
1. Bump pod limits: `resources.limits.memory: 16Gi` in the worker pod template.
2. Reduce feature cardinality by binning rare categories before encoding.
3. Switch XGBoost to `tree_method=hist` with `max_bin=128` (already default; verify).

For runaway HPO:
1. Fix the param grid.
2. Re-run with `airflow dags clear training_pipeline -s {ds} -t train_models.xgb`.
3. Add a unit test that asserts each param value is below a sane threshold (`assert max(grid["n_estimators"]) <= 500`).

For tracking-server deadlock: see §3.

**Prevention**: set `execution_timeout=timedelta(minutes=30)` on training tasks. Better to fail loudly than burn a node for an hour.

---

## 8. GPU node pool exhausted

### Symptom

(Applies if you've added GPU training, which the baseline project doesn't but many forks do.)

```
0/12 nodes are available: 12 Insufficient nvidia.com/gpu
```

The training pod is `Pending`. Other GPU workloads are running normally on the cluster.

### Diagnosis

```bash
# How many GPUs total, and how many used?
kubectl get nodes -l nvidia.com/gpu.present=true -o json | jq '
  .items[] | {
    name: .metadata.name,
    capacity: .status.capacity["nvidia.com/gpu"],
    allocatable: .status.allocatable["nvidia.com/gpu"]
  }
'

# Who's using them?
kubectl get pods --all-namespaces -o json | jq '
  .items[] | select(.spec.containers[].resources.limits["nvidia.com/gpu"]) | {
    namespace: .metadata.namespace,
    name: .metadata.name,
    gpus: .spec.containers[0].resources.limits["nvidia.com/gpu"],
    age: .status.startTime
  }
'
```

Common causes:
- Jupyter notebooks holding 4 GPUs each, idle, for days.
- Failed training jobs left behind because `cleanup_pods_on_failure=False`.
- Cluster autoscaler hit the node pool ceiling.

### Remediation

Immediate:
1. Identify and reap idle/zombie GPU pods. Notebooks should have an `idle-timeout` sidecar (see `kubernetes/jupyter/` if used).
2. If the autoscaler is at its ceiling, raise it temporarily (cloud-provider-specific).

Medium-term:
1. Move GPU training to a dedicated node pool with taints, so CPU workloads can't pre-empt or starve it.
2. Use [Kueue](https://kueue.sigs.k8s.io/) or a similar gang-scheduler so GPU training jobs queue cleanly instead of failing.
3. Time-share via MIG (Multi-Instance GPU) on A100/H100 for smaller training runs.

**Don't** make Airflow retry GPU-pending tasks aggressively — you'll thrash the scheduler. Use `retries=1` with a long `retry_delay` so the cluster has time to scale up.

---

## 9. Drift detector false positives

### Symptom

The drift detector reports `feature_drift_score > 0.1` for a feature every day. The on-call engineer triages, finds the data is fine, and ignores it. Eventually a real drift event happens and gets ignored too. Alert fatigue achieved.

### Diagnosis

Look at the per-feature scores over 30 days:

```promql
quantile_over_time(0.5, feature_drift_score{feature="tenure"}[30d])
```

If the median score is consistently near the threshold (0.1) with daily spikes above, the threshold is wrong for that feature, not that the feature is actually drifting.

The KS test and JS divergence both have non-trivial sample-size sensitivity: a feature with low daily volume produces noisier scores. A flat threshold across all features will misbehave.

### Remediation

1. Per-feature thresholds. Compute the 99th-percentile drift score over a 30-day calibration window for each feature, then set the alert threshold to that:
   ```python
   feature_thresholds = {
       feature: np.percentile(historical_scores[feature], 99)
       for feature in features
   }
   ```
2. Require **3 consecutive days** above threshold before alerting. One-off spikes are usually data hiccups, not drift.
3. Use **windowed drift** (compare last 7 days to the trailing 30 days) rather than day-over-day. Smoother, captures real shifts.
4. Distinguish *covariate drift* (feature distribution change) from *concept drift* (label distribution change given features). The former is noisy; the latter directly affects model performance and is the one worth waking someone up for.

**Prevention**: every new alert goes through a 1-week shadow period where it fires to a low-signal channel before promoting to PagerDuty. If it false-positives more than 2× during that week, tune before promoting.

---

## 10. Stuck DAG run (no progress, no error)

### Symptom

Airflow UI shows the DAG run as `running` for hours. The current task is stuck in `queued` or `running` with no log output. No error in the scheduler log.

### Diagnosis

```bash
# Is the scheduler alive and processing?
kubectl -n airflow logs deploy/airflow-scheduler --tail=100 | grep -i error

# Are the executor pods being created?
kubectl -n airflow get pods | grep <task_id>

# If executor pod exists but is Pending:
kubectl -n airflow describe pod <pod_name> | tail -30
```

Common causes:
- KubernetesExecutor cannot schedule the worker pod (node selector too restrictive, taints not tolerated, resources unavailable).
- The task is waiting on an XCom from a previous task that completed but didn't push the value.
- A `KubernetesPodOperator`'s spawned pod was deleted out-of-band and the operator is polling for a pod that no longer exists.
- The scheduler itself has stalled (rare in Airflow 2.6+ but possible under DB contention).

### Remediation

1. If the executor pod is Pending: address the scheduling constraint (more nodes, fix taints).
2. If the operator is waiting for a vanished pod:
   ```bash
   airflow tasks state <dag_id> <task_id> <run_id>      # see what it thinks
   airflow tasks failed <dag_id> <task_id> <run_id>     # mark failed, allow retry
   ```
3. If the scheduler is stalled: restart it (`kubectl -n airflow rollout restart deploy/airflow-scheduler`). With 2 scheduler replicas, this is zero-downtime.
4. Always check Airflow's "Deadlocks" view at `/dagrun/`. A common deadlock is two `TriggerDagRunOperator`s waiting on each other.

**Prevention**: set `execution_timeout` on every task. Even an absurdly long timeout (24 hours) is better than no timeout, because it surfaces stuck runs in the alerting system rather than hiding them.

---

## 11. Postgres connection pool exhausted

### Symptom

Both Airflow and MLflow start throwing `OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections`. New tasks queue up; the UI gets slow.

### Diagnosis

```sql
-- Connect to Postgres as superuser
SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname ORDER BY count DESC;
SELECT usename, application_name, count(*) FROM pg_stat_activity GROUP BY 1, 2 ORDER BY count DESC;
```

If `airflow` user has 200 connections out of `max_connections=200`, the Airflow scheduler is leaking connections. Possible causes:

- A high `parallelism` setting (`parallelism=512`) with each worker holding multiple connections.
- A custom operator that opens a connection per task and forgets to close it.
- `KubernetesPodOperator` pods running `airflow tasks run` and each spawning its own connection pool.

### Remediation

Immediate:
```sql
-- Kill idle connections older than 5 minutes
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < now() - interval '5 minutes'
  AND usename = 'airflow';
```

Short-term: bump `max_connections` (requires Postgres restart). Quick win but doesn't fix the leak.

Real fix:
1. Put PgBouncer in front of Postgres (the Airflow Helm chart has `pgbouncer.enabled: true`). PgBouncer multiplexes — 1000 client connections fan into 20 server connections.
2. Audit custom operators for `Hook.get_conn()` calls without `with` blocks.
3. Reduce `parallelism` to a sane value (`64` is plenty for most workloads).

**Prevention**: pgBouncer from day one. The cost of running it is negligible; the cost of not having it during an incident is high.

---

## 12. Silent serving regression after rollout

### Symptom

Deployment DAG ran green. Prometheus shows the new version is serving traffic. Engineers are happy. A week later, somebody notices the business KPI (e.g. churn save rate) has declined by 4%.

This is the worst failure mode because it doesn't trigger any alert — the model is "working" by every technical metric.

### Diagnosis

You need historical predictions you can compare. If `predictions/{model_version}/` is partitioned by model version (which our pipeline does), you can compute:

```sql
-- pseudo-SQL against the predictions+labels join
SELECT model_version,
       AVG(CASE WHEN prediction > 0.5 THEN actual_churn END) AS precision_proxy,
       AVG(prediction) AS mean_score
FROM predictions p
JOIN labels l USING (customer_id, ds)
WHERE ds > current_date - 60
GROUP BY model_version;
```

If the new version has a lower precision_proxy or a meaningfully shifted mean_score, that's your regression. Cross-check with the shadow-comparison report from the deployment DAG to see whether the disagreement segment correlates with the affected business segment.

### Remediation

1. Roll back via the blue/green mechanism (the inactive color is still running for `ROLLBACK_WINDOW_MINUTES`; if longer than that, redeploy the previous version from the registry):
   ```bash
   ./scripts/promote-model.sh churn-classifier <previous_version> --rollback
   ```
2. Add a post-deployment monitor that compares the new model's predictions to the old model's predictions on a holdback sample for at least 7 days. Flag any divergence above 5%.
3. Add business-KPI metrics to Grafana with a 14-day rolling comparison and alert on >2% week-over-week change.

**Prevention**: this is the gap between "the model works" (technical) and "the model is good" (business). Closing it requires a feedback loop from real labels — which arrive 30–90 days late for churn. Therefore:

- Maintain a holdback group that never gets the new model's predictions, so you have an untreated baseline.
- Decide acceptable A/B comparison windows in advance, not in panic.
- Treat champion-challenger as a 30-day commitment, not an instant cutover. The pipeline's blue/green is the technical substrate; the *decision* to keep or revert the new version is a business decision that needs business data.

---

## Quick recovery commands

When in doubt, this is the recovery cookbook in priority order:

```bash
# 1. What's red?
kubectl get pods --all-namespaces | grep -vE "(Running|Completed)"

# 2. Recent Airflow failures
docker-compose exec airflow-webserver \
  airflow dags list-runs --state failed --limit 10

# 3. Recent MLflow runs
mlflow runs search --experiment-name churn-prod-platform \
  --order-by 'attribute.start_time DESC' --max-results 5

# 4. Are the Production model and the serving pod's model the same version?
diff <(mlflow models describe -n churn-classifier --stage Production | jq -r '.version') \
     <(kubectl -n ml-serving exec deploy/predictor-blue -- printenv MODEL_VERSION)

# 5. Reset the local dev stack (last resort)
make docker-down && make clean && make docker-build && make docker-up
```

If none of these get you unstuck, escalate. A stuck pipeline is fixable; a pipeline that's been "patched" by someone who didn't understand the failure is much harder to recover.
