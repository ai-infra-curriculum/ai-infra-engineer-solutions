# Structured Log Pipeline (Loki + Vector) — Solution

Reference for [learning exercise-05](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-05-log-pipeline/README.md).

End-to-end pipeline: Python → Vector → Loki → Grafana, with trace correlation + retention tiering + cardinality control.

## Layout

```
exercise-05-log-pipeline/
├── README.md, requirements.txt
├── app.py                       # structured JSON logging
├── vector.toml                  # Vector pipeline
├── loki-config.yaml             # Loki with retention rules
└── docker-compose.yaml
```

## Run

```bash
docker compose up -d
python app.py                     # emits structured logs
open http://localhost:3000        # Grafana Explore → Loki
```
