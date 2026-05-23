# Cost-Aware LLM Routing — Solution

Reference for [learning exercise-08](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-08-llm-cost-routing/README.md).

3-tier routing with confidence-based escalation.

## Files

- `router.py` — FastAPI router with tier selection + escalation
- `classifier.py` — heuristic + small-LLM classifier
- `tiers.yaml` — tier definitions + cost rates
- `RESULTS.md` — measured cost savings
