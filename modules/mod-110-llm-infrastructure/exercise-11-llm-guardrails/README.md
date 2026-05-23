# LLM Guardrails — Solution

Reference for [learning exercise-11](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-11-llm-guardrails/README.md).

Defense in depth: input sanitization + moderation + output filtering + schema-constrained output + refusal patterns.

## Files

- `guardrails.py` — composable Guard pipeline (Pre + Post)
- `attack_suite.py` — 25 known attack patterns to test against
- `RESULTS.md` — blocked / passed / false-positive counts
