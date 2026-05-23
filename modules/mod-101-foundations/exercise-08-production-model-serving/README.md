# model-serve — Production-Grade FastAPI Model Serving — Solution

Reference solution for [learning exercise-08-production-model-serving](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-101-foundations/exercises/exercise-08-production-model-serving/README.md).

Implements the 15 requirements: app factory, validated routes, graceful shutdown, structured logs, rate limit, request-id, body-size limit, Prometheus metrics, health/ready probes, admin reload, batch endpoint, Dockerfile (non-root, read-only fs).

## Layout

```
exercise-08-production-model-serving/
├── README.md, requirements.txt
├── pyproject.toml
├── Dockerfile, docker-compose.yml
├── src/model_serve/
│   ├── __init__.py
│   ├── app.py             # FastAPI factory + lifespan
│   ├── config.py          # pydantic-settings
│   ├── logging_config.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── predict.py
│   │   └── admin.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── request_id.py
│   │   ├── body_size.py
│   │   └── rate_limit.py
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── schemas.py
│   └── instrumentation.py
└── tests/
    ├── conftest.py
    └── test_routes.py
```

## Quick start

```bash
./scripts/setup.sh
export MODEL_PATH=tests/fixtures/model.joblib
export FEATURE_COUNT=4
uvicorn model_serve.app:app --port 8000
curl -X POST localhost:8000/v1/predict -H 'content-type: application/json' \
  -d '{"features":[5.1,3.5,1.4,0.2]}'
```

Or via Docker:
```bash
docker compose up --build
```
