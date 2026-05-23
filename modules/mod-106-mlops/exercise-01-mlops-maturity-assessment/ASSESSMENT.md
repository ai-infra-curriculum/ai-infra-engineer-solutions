# MLOps Maturity Assessment — Sample Output

Reference for [learning exercise-01](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-01-mlops-maturity-assessment/README.md).

Team profile: mid-size data team, 4 ML engineers, 3 production models, currently doing model deploys via manual notebooks.

## Current level: 1 (Manual ML pipeline)

Per Google's framework:

| Capability | Current | Target (12 months) |
|---|---|---|
| Data validation | manual | automated (Great Expectations) |
| Feature engineering | per-notebook | feature store (Feast) |
| Model training | notebook | DVC-tracked pipeline |
| Experiment tracking | spreadsheet | MLflow |
| Model registry | filesystem | MLflow registry |
| CI/CD for models | none | GitHub Actions + canary |
| Production monitoring | model latency only | drift + bias + slice metrics |
| Triggered retraining | manual | event + cron driven |

## Top 5 next investments (priority order)

1. **MLflow tracking** (2 weeks) — Foundation for everything else. Even basic logging beats spreadsheets.
2. **DVC for data + model versioning** (3 weeks) — Solves "what data trained this model" question forever.
3. **Model registry + staging promotion** (2 weeks) — Eliminates "which model is in prod?" ambiguity.
4. **CI for model code** (2 weeks) — Catches regressions before they reach prod.
5. **Production drift monitoring** (4 weeks) — Surface degradation before customers do.

## 6-month roadmap

| Month | Investment | Owner | Outcome |
|---|---|---|---|
| 1 | MLflow + tracking server | platform | every training run logged |
| 1-2 | DVC for one pipeline (proof) | ML eng A | reproducible training, audit trail |
| 2 | Model registry workflow | ML eng B | manual promotion w/ history |
| 3 | CI pipeline (lint, test, validate) | platform | regressions caught at PR time |
| 3-4 | Feature store (Feast) | ML eng C | training/serving skew eliminated |
| 4-5 | Drift + monitoring | platform | dashboard + alerts |
| 6 | Canary deployments | platform | safer rollouts |

## Maturity transition

After 6 months: Level 2 (ML pipeline automation) for the first model.
After 12 months: Level 2 across all models; Level 3 (CI/CD automation) for the model with most traffic.
