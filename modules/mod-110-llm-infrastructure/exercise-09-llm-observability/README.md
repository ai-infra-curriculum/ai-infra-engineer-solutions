# LLM-Specific Observability — Solution

Reference for [learning exercise-09](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-09-llm-observability/README.md).

## Files

- `instrument.py` — middleware capturing LLM-specific signals
- `metrics.py` — Prometheus metrics defs (TTFT, tokens/s, prompt + completion lengths)
- `sampling_logger.py` — log 1% of prompt+response pairs to S3
- `dashboard.json` — Grafana panels
- `alerts.yml` — LLM-specific alerts (TTFT degradation, runaway prompts)
