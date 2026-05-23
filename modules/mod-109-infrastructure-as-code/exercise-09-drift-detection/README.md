# Drift Detection — Solution

Reference for [learning exercise-09](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-09-drift-detection/README.md).

## Files

- `drift_check.py` — runs `terraform plan` across all projects + posts diff to Slack
- `classify.py` — severity classification (cosmetic / material / critical)
- `ci-examples/drift.yml` — nightly drift-detection GHA workflow
- `REMEDIATION.md` — playbook for adopting vs reverting changes
