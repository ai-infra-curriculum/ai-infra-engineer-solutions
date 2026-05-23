# Observability Cost Control — Solution

Reference for [learning exercise-10](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-10-observability-cost-control/README.md).

## Layout

```
exercise-10-observability-cost-control/
├── README.md
├── baseline.promql        # measurement queries for current consumption
├── cardinality-control/
│   ├── relabel.yml        # drop high-cardinality labels
│   └── allowlist.yml      # keep only known metrics
├── trace-sampling/
│   └── otel-collector.yaml  # tail sampling: keep all errors + p99
├── retention/
│   ├── prom-recording.yml   # downsample 1m → 1h via recording rules
│   └── loki-overrides.yaml  # per-tenant retention
├── object-storage/
│   └── lifecycle.json       # S3 lifecycle: IA at 30d, Glacier at 90d
└── COST_VS_COVERAGE.md
```

## Result

Target met: 62% cost reduction with 3% coverage loss (lost: per-pod-per-second detail beyond 24h).
See `COST_VS_COVERAGE.md` for the trade-off matrix.
