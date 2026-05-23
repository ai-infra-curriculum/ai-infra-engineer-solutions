# Pipeline Monitoring + Lineage (OpenLineage + Marquez) — Solution

Reference for [learning exercise-08](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-08-pipeline-monitoring-lineage/README.md).

## Layout

```
exercise-08-pipeline-monitoring-lineage/
├── README.md
├── airflow_openlineage.cfg     # Airflow OpenLineage config
├── prom/
│   ├── exporter.py             # exports per-task metrics
│   └── alerts.yml              # freshness SLO + failure alerts
├── marquez/docker-compose.yaml
├── queries/                    # column-lineage example queries
└── grafana-dashboard.json
```
