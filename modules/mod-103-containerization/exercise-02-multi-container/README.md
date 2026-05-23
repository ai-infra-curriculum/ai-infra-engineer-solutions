# Multi-Container ML Stack — Solution

Reference for [learning exercise-02](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-02-multi-container.md).

FastAPI + Postgres + Redis + Prometheus.

```bash
docker compose up -d
curl -X POST localhost:8000/predict -H 'content-type: application/json' \
  -d '{"features":[1,2,3,4]}'
open http://localhost:9090
```
