# SLO + Error Budget Implementation — Solution

Reference for [learning exercise-08](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-08-slo-and-error-budgets/README.md).

## Layout

```
exercise-08-slo-and-error-budgets/
├── README.md
├── sli-rules.yml
├── slo-config.yml             # Sloth-format SLO spec
├── budget-burn-alerts.yml
├── grafana-budget-panel.json
└── QUARTERLY_REVIEW_TEMPLATE.md
```

## Targets

- **Availability SLO:** 99.5% of requests succeed (non-5xx) over 30d
- **Latency SLO:** 95% of requests under 200ms over 30d

## Workflow

1. Define SLIs as recording rules (`sli-rules.yml`)
2. Set SLO targets (`slo-config.yml`)
3. Load multi-window burn-rate alerts (`budget-burn-alerts.yml`)
4. Track in Grafana (`grafana-budget-panel.json`)
5. Review quarterly (`QUARTERLY_REVIEW_TEMPLATE.md`)
