# Distributed Tracing with OpenTelemetry — Solution

Reference for [learning exercise-06](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-06-distributed-tracing-otel/README.md).

Three-service Python stack instrumented with OTel, traces to Tempo, logs correlated by trace_id.

## Layout

```
exercise-06-distributed-tracing-otel/
├── README.md, requirements.txt
├── frontend.py, backend.py, feature_store.py
├── otel_setup.py            # shared init
├── tempo.yaml
└── docker-compose.yaml
```

## Run

```bash
docker compose up -d
python frontend.py            # emits a couple of requests
open http://localhost:3000    # Grafana → Tempo → search
```
