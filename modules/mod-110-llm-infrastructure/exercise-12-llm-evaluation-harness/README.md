# LLM Scoring Harness — Solution

Reference for [learning exercise-12](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-12-llm-evaluation-harness/README.md).

Reproducible scoring of LLM apps using LLM-as-judge + reference-based metrics.
Tracked over time; CI fails on regression.

## Files

- `run.py` — runs the scoring suite
- `judge.py` — LLM-as-judge calls
- `reference.py` — BLEU + ROUGE + exact-match metrics
- `golden_set.jsonl` — example test cases
- `track.py` — append scores to history.jsonl + plot
