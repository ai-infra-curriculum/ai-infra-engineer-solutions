# Model Registry + Promotion Workflow — Solution

Reference for [learning exercise-03](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-03-model-registry-promotion/README.md).

## Files

- `promote.py` — quality gate + promotion to Staging or Production.
- `rollback.py` — atomic rollback to previous Production version.
- `audit.py` — emit promotion events to an append-only audit log.
- `slack_approval.py` — gate Production with manual Slack approval.

## Workflow

```bash
python promote.py iris-rf 15 --to staging         # auto if quality OK
python slack_approval.py iris-rf 15 --to production    # waits for #ml-platform thumbs-up
python rollback.py iris-rf                              # to last-good Production version
python audit.py log                                     # dump audit trail
```
