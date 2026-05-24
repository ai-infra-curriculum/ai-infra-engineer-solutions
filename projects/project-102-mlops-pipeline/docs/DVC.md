# DVC Guide

[DVC 3.30.1](https://dvc.org) is used in this project for **data and model versioning** alongside Git. It is intentionally not the only versioning mechanism — MLflow handles experiment artifacts, and S3/MinIO handles raw storage. DVC's job is to give us a Git-native way to refer to a specific dataset or model state by content hash, and to make `dvc.yaml` pipelines reproducible across environments.

If you've used Git LFS and walked away unimpressed, DVC is what you actually wanted: content-addressed storage with proper remote backends, dependency tracking, and pipeline DAGs.

---

## 1. Why DVC alongside MLflow?

A reasonable first question is "doesn't MLflow already track artifacts?" Yes — but for different purposes:

| | MLflow | DVC |
|---|--------|-----|
| Primary unit | Run / model version | File or directory |
| Storage backend | S3/MinIO under `mlflow/` | S3/MinIO under `dvc-cache/` |
| Versioning model | Append-only, indexed by run id | Content hash, indexed by `.dvc` pointer in Git |
| Reproducibility | "What params produced this model?" | "What inputs produced this preprocessing output?" |
| Discovery | UI + Python API | Git log + `dvc list` |
| Pipeline DAG | Airflow | `dvc.yaml` (for local repro) |

The boundary we draw: **MLflow owns trained models and experiment metadata. DVC owns raw and intermediate datasets.** A model in the MLflow registry has a `dvc_pointer` tag that links back to the exact features `.dvc` file. A `.dvc` file in Git points to the actual data in MinIO.

This means: a developer can `git checkout` a 6-month-old commit, `dvc pull`, and get the exact features that produced the model logged on that commit's CI run. Without DVC, "the data from last quarter" is a folder somewhere with no guarantees of immutability.

---

## 2. Remote storage setup

The DVC remote is the `dvc-cache` bucket on MinIO. Configuration in `.dvc/config`:

```ini
[core]
    remote = minio
    autostage = true

['remote "minio"']
    url = s3://dvc-cache
    endpointurl = http://minio.mlops-system.svc.cluster.local:9000
    use_ssl = false
    listobjects = true
```

Credentials are read from environment (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or `~/.aws/credentials` — DVC delegates to `boto3`. In CI, they come from a GitHub Actions secret bound to a dedicated MinIO user with `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` on the `dvc-cache` bucket and nothing else.

### 2.1 Concurrent access

DVC's S3 backend uses object-level atomicity: each blob is written under its content hash, so two clients pushing the same blob simply race and both succeed (the second one is a no-op overwrite of identical bytes). There is no global lock. This works because:

- Blobs are immutable (content-addressed).
- Pointer files (`.dvc`) are tracked in Git; Git handles concurrency.
- Stage files (`dvc.yaml`, `dvc.lock`) are also Git-tracked.

If two CI jobs are pushing different data with the same logical path, the conflict is on the Git side (merge conflict in `.dvc` or `dvc.lock`), not on the storage side. This is correct behavior and we want the human to resolve it.

### 2.2 Permissions per environment

| Environment | Bucket policy |
|-------------|---------------|
| Local developer | Read-only on `dvc-cache` |
| CI training job | Read/write on `dvc-cache` |
| Production data pipeline | Read/write on `dvc-cache` |
| Predictor service | No DVC access at all — pulls models from MLflow only |

Restricting local developers to read-only is deliberate: it prevents an accidental `dvc push` from someone's laptop from contaminating the shared cache. The "right" way to publish new data is via CI.

---

## 3. Pipeline definition (`dvc.yaml`)

DVC can encode the same pipeline as Airflow, but at a much finer granularity and meant for local reproduction. We use it sparingly — only for the data preprocessing stages, which we want runnable on a developer laptop.

```yaml
# dvc.yaml
stages:
  ingest:
    cmd: python -m src.data.ingestion --output data/raw/
    deps:
    - src/data/ingestion.py
    - src/common/storage.py
    params:
    - ingestion.sources
    outs:
    - data/raw/

  validate:
    cmd: python -m src.data.validation --input data/raw/ --output data/validated/
    deps:
    - data/raw/
    - src/data/validation.py
    outs:
    - data/validated/
    metrics:
    - reports/validation.json:
        cache: false

  preprocess:
    cmd: python -m src.data.preprocessing --input data/validated/ --output data/features/
    deps:
    - data/validated/
    - src/data/preprocessing.py
    params:
    - preprocessing
    outs:
    - data/features/
    - models/transformer.joblib

  train:
    cmd: python -m src.training.trainer --features data/features/ --model-out models/champion.joblib
    deps:
    - data/features/
    - models/transformer.joblib
    - src/training/trainer.py
    - src/training/evaluator.py
    params:
    - training
    outs:
    - models/champion.joblib
    metrics:
    - reports/training_metrics.json:
        cache: false
    plots:
    - reports/confusion_matrix.png:
        cache: false
```

Run the full pipeline with `dvc repro`. DVC computes a dependency graph from `deps`/`outs` and only re-runs stages whose inputs (files **or** params) have changed.

### 3.1 `dvc.lock`

After each run, `dvc.lock` records the actual hash of every dep and out. Committing this file is what gives you reproducibility: a teammate's `dvc repro` is a no-op if their checkout matches the lock.

### 3.2 Parameters

`params.yaml`:

```yaml
ingestion:
  sources:
    - s3://raw/crm-2026
    - s3://raw/billing-2026

preprocessing:
  imputation_strategy: median
  categorical_encoder: one_hot
  scaling: standard

training:
  cv_folds: 5
  random_state: 42
  models:
    - logreg
    - rf
    - gbm
    - xgb
  hpo_iter: 20
```

DVC tracks dependencies on specific keys, so changing `preprocessing.scaling` invalidates only `preprocess` and `train`, not `ingest` or `validate`. This is finer-grained than tracking the whole `params.yaml` file.

---

## 4. Reproducibility patterns

### 4.1 "Reproduce the model from commit `abc123`"

```bash
git checkout abc123
dvc pull              # downloads data + intermediate artifacts referenced by the lock
dvc repro             # no-op if lock matches; otherwise replays missing stages
mlflow ui             # see the runs that produced the committed metrics
```

This works because:

- `git checkout` brings back the code, params, and `.dvc` pointers.
- `dvc pull` materializes the exact files those pointers reference.
- `dvc repro` is deterministic given identical inputs.

If the pull fails because the cache has been GC'd (see §6), you can still rebuild from raw — `dvc repro` will replay `ingest` from the upstream sources. This is why we keep `ingest` source URIs immutable: a 6-month-old commit's `params.yaml` references `s3://raw/crm-2026` which must still exist.

### 4.2 "Change one preprocessing param and retrain"

```bash
# Edit params.yaml: preprocessing.scaling = robust
dvc repro train       # DVC sees the changed param; re-runs preprocess + train
git add params.yaml dvc.lock
git commit -m "Try robust scaling for skewed features"
dvc push              # pushes the new outputs to the remote cache
git push
```

Now anyone who checks out this commit and runs `dvc pull` gets the same outputs without rerunning. The CI job for this commit creates an MLflow run with the new params tagged.

### 4.3 "Compare two model versions on the same data"

```bash
# Get the data hash from the model's MLflow tag
mlflow runs describe --run-id <run_id_v1> | jq '.data.tags["dataset_hash"]'
mlflow runs describe --run-id <run_id_v2> | jq '.data.tags["dataset_hash"]'

# If hashes match, the comparison is apples-to-apples
# If not, you must reconstruct the older dataset:
git checkout $(git log --all --grep="dvc_pointer:<hash>" --format=%H -n 1)
dvc pull data/features/
```

The `dataset_hash` tag is set by the training code from `dvc.api.read_dvc_meta()` of the input directory. This gives us cross-tool linking: MLflow tag → DVC hash → Git commit.

---

## 5. DVC and Git interplay

The two tools have separate but synchronized states. The mental model:

| Git tracks | DVC tracks |
|------------|------------|
| Code | Data |
| `.dvc` pointer files | The actual data blobs (in the remote) |
| `dvc.yaml`, `dvc.lock` | Pipeline stage outputs |
| `params.yaml` | (DVC reads it for invalidation) |

A `.dvc` file looks like:

```yaml
outs:
- md5: 8f3e8a2c1b9d4e5f6a7b8c9d0e1f2a3b.dir
  size: 47382911
  nfiles: 12
  hash: md5
  path: features
```

This file (~200 bytes) lives in Git. The 47 MB it describes lives in MinIO under `dvc-cache/8f/3e8a2c1b9d4e5f6a7b8c9d0e1f2a3b.dir`. When you `git pull`, you get the pointer. When you `dvc pull`, you get the data.

### 5.1 `.gitignore`

DVC auto-manages `.gitignore` entries so that data directories don't accidentally get committed to Git. The `.dvcignore` file works the opposite way — patterns DVC should not include when computing hashes (e.g. `*.tmp`, `.ipynb_checkpoints`).

### 5.2 Branches and merging

Each branch can have its own data state. A feature branch experimenting with new features will have a different `dvc.lock` and different `.dvc` pointers; the data blobs themselves are shared if content overlaps (the whole point of content addressing).

Merging branches: Git handles `.dvc` and `dvc.lock` conflicts as normal text conflicts. After resolving, run `dvc checkout` to materialize the merged state. If both branches modified the same data directory, the merge resolution determines which version wins — there is no automatic "merge" of data contents.

### 5.3 Pre-commit hook

`.git/hooks/pre-commit` (installed via `pre-commit` framework):

```yaml
repos:
  - repo: https://github.com/iterative/dvc
    rev: 3.30.1
    hooks:
      - id: dvc-pre-commit          # blocks commits that lose DVC pointer integrity
      - id: dvc-pre-push            # ensures `dvc push` runs before `git push`
      - id: dvc-post-checkout       # runs `dvc checkout` after `git checkout`
```

The `dvc-pre-push` hook is the important one: it prevents you from pushing a Git commit that references DVC objects which are only in your local cache. Without it, teammates will `git pull` then see "missing blob" errors.

---

## 6. Cache management at scale

The DVC cache grows monotonically until you GC. Two caches:

- **Local cache** (`.dvc/cache/`): on the developer's laptop or CI runner. Cleaned by `dvc gc -w` (workspace only) or `dvc gc -a` (all references).
- **Remote cache** (`s3://dvc-cache/`): the shared state. Cleaned by `dvc gc -r minio -a`.

### 6.1 Local GC

On developer laptops, run weekly:

```bash
dvc gc --workspace    # keep only what the current branch needs
```

This typically reclaims 10–50 GiB. It's safe because anything GC'd locally can be re-pulled from the remote.

### 6.2 Remote GC

Remote GC is **dangerous** because it deletes blobs other people may still reference. Our policy:

- Only run via the scheduled CronJob `dvc-gc-weekly` in the `mlops-system` namespace.
- The CronJob runs `dvc gc -r minio --all-commits --not-in-remote` — keeps everything referenced by any commit in the remote Git repo.
- Excluded commits: anything tagged `release/*` or referenced by an MLflow Production model's `dvc_pointer` tag. The script enumerates these and passes them to `dvc gc --rev`.

```bash
# kubernetes/cronjobs/dvc-gc.sh
PROD_DVC_REFS=$(
  curl -s -u $MLFLOW_USER:$MLFLOW_PASS \
    https://mlflow.example.com/api/2.0/mlflow/registered-models/search \
    | jq -r '.registered_models[].latest_versions[] | select(.current_stage == "Production") | .tags[] | select(.key == "dvc_pointer") | .value'
)
RELEASE_TAGS=$(git tag -l 'release/*' | tr '\n' ' ')

dvc gc -r minio --all-commits --rev "$PROD_DVC_REFS $RELEASE_TAGS"
```

The first time we ran this on a 6-month-old project, it reclaimed 1.2 TiB. The naive `dvc gc --workspace -r minio` would have nuked everything reachable only from older Git commits, including data referenced by an old Production model we needed for a regression investigation. The `--all-commits` + explicit `--rev` pattern is what saved us.

### 6.3 Cache size monitoring

Prometheus scrapes MinIO's `/minio/v2/metrics/cluster`:

```
mlflow_dvc_cache_bytes = sum by (bucket) (minio_bucket_usage_object_total{bucket="dvc-cache"})
```

Alert at >80% of the bucket quota. The dashboard panel "DVC cache growth (30d)" makes it obvious when a careless commit checked in a huge unintended directory.

### 6.4 Deduplication

Content-addressed storage gives free deduplication: two files with identical bytes share one blob. This matters at the directory level too — `dvc add data/features/` creates a `.dir` blob that lists per-file hashes, so adding a new partition to an existing directory only stores the new files.

In practice, a `data/features/` directory that grows by ~5% per week with weekly snapshots only grows the cache by ~5% per snapshot, not 100%.

---

## 7. Common DVC anti-patterns to avoid

- **`dvc add` on a directory with mixed mutable and immutable contents**: DVC will track the whole thing. Split mutable working files into a separate `.gitignored` directory.
- **Running `dvc push` from a developer laptop without coordination**: contaminates the shared cache with non-CI data. Lock developers to read-only on the remote.
- **Storing model binaries in DVC instead of MLflow**: works, but you lose the registry semantics (stages, lineage, search). Use DVC for data, MLflow for models, and link them via tags.
- **Forgetting to `dvc pull` after `git checkout`**: stale data with new code. The `dvc-post-checkout` Git hook fixes this automatically.
- **Hardcoding data paths in code instead of using `dvc.api.open()` or `params.yaml`**: breaks the DVC dependency graph; `dvc repro` won't know to re-run dependent stages.

---

## 8. Quick reference

```bash
# Track a new directory
dvc add data/new_dataset/

# Push tracked data to remote
dvc push

# Pull tracked data from remote
dvc pull

# Run / re-run the pipeline (only stages with changed deps)
dvc repro

# Force re-run a specific stage even if deps unchanged
dvc repro -f train

# Show what would re-run
dvc status

# Compare metrics across commits
dvc metrics diff HEAD~5

# Visualize the pipeline DAG
dvc dag

# Show data lineage of an output
dvc dag --outs models/champion.joblib

# Disk usage of cache
du -sh .dvc/cache/

# What's in the remote?
dvc list . --dvc-only --recursive

# Garbage collect local cache
dvc gc --workspace
```

If you remember three commands: `dvc add`, `dvc push/pull`, `dvc repro`. Everything else is for special occasions.
