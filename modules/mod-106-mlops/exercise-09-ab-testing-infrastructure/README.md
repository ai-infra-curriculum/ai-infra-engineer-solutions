# A/B Testing Infrastructure — Solution

Reference for [learning exercise-09](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-09-ab-testing-infrastructure/README.md).

Consistent assignment + exposure logging + downstream attribution + statistical analysis.

## Files

- `assignment.py` — consistent hashing per user_id
- `serving_wrapper.py` — FastAPI wrapper that picks variant + logs exposure
- `analyze.py` — Mann-Whitney U + Welch's t-test + effect size
- `experiments.yaml` — declarative experiment config
