# MLflow Tracking Deep Dive — Solution

Reference for [learning exercise-02](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-02-mlflow-tracking-deep-dive/README.md).

## Layout

```
exercise-02-mlflow-tracking-deep-dive/
├── README.md, docker-compose.yaml      # Postgres + MinIO + tracking server
├── train.py                             # autolog + custom metrics + signature
├── pyfunc_model.py                      # custom packaging
└── deploy_server.sh
```

## Run

```bash
docker compose up -d                   # tracking server + postgres + minio
export MLFLOW_TRACKING_URI=http://localhost:5000
python train.py
mlflow ui --backend-store-uri postgresql://... --port 5000
```
