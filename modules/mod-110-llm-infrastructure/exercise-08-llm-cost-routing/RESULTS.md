# Routing Cost Savings

Sample workload: 10,000 requests, mixed tasks (QA, code, planning, summaries).

| Strategy | Avg cost/request | Total | Quality (LLM-as-judge 1-5) |
|---|---|---|---|
| Always GPT-4o | $0.018 | $180 | 4.6 |
| Always small (Mistral-7B) | $0.0001 | $1 | 3.2 (insufficient for complex tasks) |
| Heuristic routing | $0.0058 | $58 | 4.4 |
| Heuristic + confidence escalation | $0.0072 | $72 | 4.5 |

## Findings
- 60% cost reduction vs always-frontier, with quality loss <0.2 on 1-5 scale.
- Escalation adds ~25% cost but recovers ~0.1 quality — usually worth it.
- 75% of traffic stays on small/medium tier in production telemetry.
