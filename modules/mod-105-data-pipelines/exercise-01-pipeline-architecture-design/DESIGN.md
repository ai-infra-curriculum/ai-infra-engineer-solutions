# Recommendation Pipeline Architecture — Solution

Reference for [learning exercise-01](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-01-pipeline-architecture-design/README.md).

## 1. Scope

Two-track pipeline serving a mid-size e-commerce homepage:
- **Batch**: daily training data + nightly model retrain
- **Streaming**: sub-minute event ingestion + real-time feature updates

## 2. Ingestion

| Source | Track | Mechanism | Rate |
|---|---|---|---|
| `events.click` / `view` / `purchase` | streaming | Kafka topic `events.v1`, JSON, schema-registry enforced | 10M/day → 120/s avg, 1000/s peak |
| `catalog.products` | batch | Daily Debezium snapshot → S3 Parquet | 500K rows/day |
| `users.profile` | batch | Daily CDC snapshot → S3 Parquet | 5M rows/day |
| `inventory.stock` | streaming | Kafka topic `inventory.v1`, key=sku | 50-200/s |

## 3. Processing

| Layer | Tool | Pattern |
|---|---|---|
| Real-time enrichment | Flink (or Spark Structured Streaming) | join events × product dimension (cached in RocksDB state) |
| Feature aggregation | Flink window state | per-user rolling 24h click count, last-purchase ts |
| Batch transformation | dbt on warehouse | session sessionization, daily user/product aggregates |
| Training data assembly | Airflow + Spark | joins all of above into model-ready Parquet |
| Model retrain | Airflow + sagemaker/kubeflow | XGBoost; runs nightly when new data is fresh |

## 4. Storage

| Layer | Choice | Rationale |
|---|---|---|
| Raw events landing | S3, partitioned by date+hour, Parquet | cheap, queryable from Athena |
| Warehouse | BigQuery (or Snowflake) | dbt-native; analyst access |
| Online features | Redis (low-latency) + DynamoDB (cold) | sub-50ms read for serving |
| Model artifacts | S3 + versioned in DVC | reproducibility |

## 5. Scheduling

- **Airflow** for batch DAGs (Kubernetes executor; ~30 concurrent tasks max).
- **Flink jobs** managed via Kubernetes operator (long-running).
- Cron triggers: ingest snapshots @ 02:00 UTC; retrain @ 04:00 UTC after fresh-data check.

## 6. Observability

| Signal | Tool |
|---|---|
| Pipeline freshness (per dataset) | Custom Prometheus exporter scraping S3 last-modified times |
| Per-task latency, success rate | Airflow → StatsD → Prometheus |
| Streaming lag (Kafka consumer) | kafka-exporter |
| Data quality | Great Expectations checkpoint per stage → Slack on fail |
| Lineage | OpenLineage → Marquez (column-level) |
| Cost | Daily BigQuery + S3 + EMR cost rollup → Grafana panel |

## 7. Failure handling

| Mode | Detection | Recovery |
|---|---|---|
| Source schema break | Schema Registry rejection | DLQ topic; alert Slack; manual triage |
| Late-arriving data | Watermarks + lateness windowing in Flink (10min grace) | event written to "late" partition; reconciled by next batch pass |
| Bad data row | GE checkpoint failure mid-DAG | DAG fails fast; alert; investigate without partial-write to warehouse |
| Compute failure | Airflow task retry (3x exponential) + alert if SLA blown | rerun; if persistent, page on-call |
| Warehouse over-budget | BigQuery cost alert | auto-throttle by capping concurrency; raise reservation if justified |
| Backfill needed | Detected by lineage system | use bounded-concurrency backfiller (mod-105 ex-09) |

## 8. Capacity + cost projection

- **Streaming**: 1 Flink job, 4 vCPU * 16GB = $0.40/h × 24 × 30 ≈ $290/mo
- **Batch (Airflow + Spark)**: 8-hour daily compute, ~$15/day = $450/mo
- **Storage**: ~2TB warm + 8TB cold S3 = $80/mo
- **Warehouse**: BigQuery on-demand, ~$300/mo at ~10TB scanned/month
- **Total**: ~$1100/mo

## 9. Migration path

1. Stand up batch DAG + warehouse first (week 1-2). Validate against existing reports.
2. Add streaming track (week 3-4). Run in shadow mode against existing real-time path.
3. Cut over serving to new feature store (week 5).
4. Decommission legacy path (week 6).

## 10. Risks

| Risk | Mitigation |
|---|---|
| Kafka rebalance during peak event burst | partitions sized for 2× peak; consumer cooperative-sticky assignor |
| Late dimension load blocks training | training DAG has 2h SLA; alert at 1.5h |
| Warehouse cost runaway from analyst queries | row-level access control + max bytes-billed budget |
| Feature drift between streaming + batch versions | identical SQL/Python transformation modules; nightly reconciliation report |
