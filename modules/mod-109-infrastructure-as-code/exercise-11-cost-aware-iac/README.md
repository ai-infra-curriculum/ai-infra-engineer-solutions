# Cost-Aware IaC (Infracost) — Solution

Reference for [learning exercise-11](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-11-cost-aware-iac/README.md).

## Files

- `budgets.yaml` — per-team monthly budgets
- `enforce.py` — compares Infracost delta against budget; fails PR if over
- `ci-examples/infracost.yml` — wires Infracost into PR flow
