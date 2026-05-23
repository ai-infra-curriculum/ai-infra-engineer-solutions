# Reproducibility Audit: {MODEL_NAME} v{VERSION}

Auditor: {NAME}    Date: {DATE}    Model age: {DAYS} days

## Inventory

| Artifact | Expected location | Found? | Notes |
|---|---|---|---|
| Code (git SHA) | git@example.com/repo @ {SHA} | ✅ / ❌ | |
| Data snapshot | dvc {DVC_PATH} | ✅ / ❌ | |
| Hyperparameters | mlflow run {RUN_ID} params | ✅ / ❌ | |
| Random seed | mlflow run {RUN_ID} param `seed` | ✅ / ❌ | |
| Library versions | mlflow run {RUN_ID} tags | ✅ / ❌ | |
| Compute spec | mlflow run {RUN_ID} tags | ✅ / ❌ | |
| Model artifact | mlflow run {RUN_ID} artifact | ✅ / ❌ | |

## Reproduction attempt

```bash
git checkout {SHA}
dvc checkout
mlflow artifacts download -r {RUN_ID} -d /tmp/reproduction/
# Recreate env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Re-run training
python -m src.train --seed 42 --config configs/{NAME}.yaml
```

## Diff vs original

| Metric | Original | Reproduction | Match? |
|---|---|---|---|
| accuracy | | | ✅ / ❌ |
| f1 | | | ✅ / ❌ |
| model file checksum | | | ✅ / ❌ |

## Gaps surfaced
- {GAP_1}

## Recommendations
- {RECOMMENDATION_1}

## Verdict
**REPRODUCIBLE | PARTIALLY_REPRODUCIBLE | NOT_REPRODUCIBLE**
