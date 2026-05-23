# Feature Store (Feast) — Solution

Reference for [learning exercise-07](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-07-feature-store-implementation/README.md).

## Layout

```
exercise-07-feature-store-implementation/
├── README.md, requirements.txt
├── feature_repo/
│   ├── feature_store.yaml        # offline=duckdb, online=redis
│   └── features.py               # entity + feature views
├── materialize.py                 # warehouse → online store
├── get_training_features.py       # point-in-time-correct training join
└── serve.py                       # online serving (redis lookup)
```
