# Lambda Architecture (Batch + Streaming) — Solution

Reference for [learning exercise-11](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-11-lambda-architecture/README.md).

## Layout

```
exercise-11-lambda-architecture/
├── README.md, RECONCILE.md
├── streaming/flink_features.py        # PyFlink: per-user 5m window
├── batch/spark_features.py            # Spark: daily corrected aggregate
├── serving/feature_store.py           # merge logic: streaming + batch
└── reconciliation/diff.py             # daily streaming-vs-batch reconciliation
```

## Layers

| Layer | Tool | Output | Latency | Accuracy |
|---|---|---|---|---|
| Batch | Spark daily | `user_features_batch_v1` (S3 Parquet) | 24h | high (full history reprocess) |
| Streaming | Flink continuous | `user_features_stream_v1` (Redis) | <1min | low (5-min window only) |
| Serving | feature_store API | `get(user_id)` returns most-recent values | n/a | merge: prefer batch, override last 24h with stream |

## Why merge by source

- Streaming computes "last 5 minutes" only — historical aggregates are missing.
- Batch covers all-time but is up to 24h stale.
- Serving merges: batch for "all-time" features, stream for "recent" features.
- Reconciliation reports daily diff to surface drift.
