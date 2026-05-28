# SOLUTION — Exercise 01: Data Pipeline Architecture Design

> Per-exercise solution for
> [learning exercise-01](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-01-pipeline-architecture-design/README.md).
> This factors the relevant pieces of the
> [module-level SOLUTION.md](../SOLUTION.md) (architecture rationale)
> together with the worked reference design in
> [`DESIGN.md`](./DESIGN.md) in this directory. Read it *after*
> attempting your own design.

## 1. Solution overview

This is a **design exercise**: produce a data-pipeline architecture
for a mid-size e-commerce recommendation system that serves a
homepage, covering ingestion, processing, storage, scheduling,
observability, failure handling, capacity/cost, and a migration
path.

The reference answer is a **two-track architecture** — a batch
track for training data and nightly retrains, and a streaming
track for sub-minute event ingestion and real-time feature
updates. The two tracks are kept in separate DAGs/services on
purpose; this is the central architectural decision and it flows
from the module rationale (see Decision 4 below).

The full worked design lives in [`DESIGN.md`](./DESIGN.md). This
document explains *why* the design is shaped the way it is, how to
validate a submission, and how a grader should score one.

## 2. Worked answer or implementation

The complete reference design — ingestion table, processing
layers, storage choices, scheduling, observability signals,
failure-mode matrix, capacity/cost projection, migration path, and
risks — is in [`DESIGN.md`](./DESIGN.md). The summary below ties
each part of that design to the architectural decision that
motivates it (decisions are drawn from the
[module-level SOLUTION.md](../SOLUTION.md)).

### Two-track shape (batch + streaming, separated)

- **Batch track**: daily snapshots of `catalog.products` and
  `users.profile` → S3 Parquet → dbt transforms in the warehouse →
  Airflow + Spark assembles model-ready training data → nightly
  XGBoost retrain.
- **Streaming track**: `events.v1` and `inventory.v1` Kafka topics
  → Flink (or Spark Structured Streaming) enrichment and windowed
  feature aggregation → online feature store (Redis hot,
  DynamoDB cold).

**Decision 4 — separate batch and streaming cleanly.** They have
different failure modes and operational characteristics (streaming
lag pages on-call; a batch miss is an email-by-9am affair). Mixing
them in one codebase causes ops confusion. Late-arriving data on
the streaming side is reconciled by a *separate* batch backfill
pass, not a hybrid pipeline.

### Idempotency and partitioning

Tasks reference the logical date (`{{ ds }}`), write to
deterministic partitioned paths (S3 partitioned by date+hour), and
use atomic rename / upsert semantics.

**Decision 1 — idempotent task design from the start.**
Orchestrators *will* retry tasks; non-idempotent tasks corrupt
state on retry. Deterministic output paths derived from the data
partition make a re-run produce identical output.

### Schema and data-quality gates

Schema Registry enforces event schemas at the edge; Great
Expectations checkpoints run per stage and fail the DAG fast on
bad data rather than partial-writing to the warehouse.

**Decision 2 — schema validation between every transform.** Schema
drift in upstream sources silently corrupts downstream models;
catching it at ingestion is cheap, finding out three weeks later
is not.

### Backfill as a first-class operation

Airflow DAGs cap concurrency (`max_active_runs`), tasks key off
the logical date, and the design points backfills at the bounded-
concurrency backfiller from exercise-09.

**Decision 3 — backfills are first-class.** Every ML team
backfills at least quarterly; designing for bounded-concurrency
replays up front avoids a later rewrite and avoids a backfill
overwhelming the cluster.

### Lineage and observability

OpenLineage events flow to Marquez (column-level); freshness,
per-task latency, Kafka consumer lag, data-quality results, and
cost rollups all surface in Prometheus/Grafana with Slack alerts.

**Decision 5 — data lineage as code.** When a downstream model
breaks, "what changed in the data?" must be answerable in seconds,
not days.

### Tool defaults (and the trade-offs accepted)

- **Airflow 2.x** as the batch orchestrator — wins on docs,
  integrations, and talent pool; patterns transfer to Prefect /
  Dagster / Argo / Temporal.
- **Spark** for 100GB+ transforms — mature catalog / Iceberg /
  Delta tooling vs. Dask.
- **Pandas tolerated under ~5GB** — what data scientists already
  know; the migration tax to Polars isn't worth it for small data.

## 3. Validation steps

This is a design artifact, so validation is a structured review of
the submission rather than a test run:

1. **Track separation** — confirm batch and streaming live in
   separate DAGs/services and that late-data handling routes to a
   batch reconciliation pass, not a hybrid pipeline.
2. **Idempotency trace** — pick any task and confirm a second run
   with the same logical date produces identical output (partition
   path is deterministic; writes are atomic rename or upsert).
3. **Schema/quality gates** — confirm a validation gate sits
   between transforms and that a failure stops the DAG before any
   partial warehouse write.
4. **Backfill** — confirm concurrency is bounded
   (`max_active_runs`/pool sizing) and tasks key off the logical
   date, never `datetime.now()`.
5. **Lineage and freshness** — confirm lineage emission and a
   per-dataset freshness signal with alerting exist.
6. **Capacity/cost sanity** — re-derive the section 8 cost math in
   [`DESIGN.md`](./DESIGN.md) from the stated rates and confirm the
   numbers are internally consistent (they are an order-of-
   magnitude estimate, not a billing guarantee).
7. **Markdown** — `markdownlint-cli2` passes (no broken links/
   empty links); see repo [`.markdownlint.jsonc`](../../../.markdownlint.jsonc).

## 4. Rubric or review checklist

Score each dimension; a strong submission addresses all six. Point
weights are pedagogical scaffolding for graders, not external
metrics.

| Dimension | Looking for | Weight |
|---|---|---|
| Ingestion & sources | Each source mapped to a track, mechanism, and rate; schema enforcement at the edge | 15 |
| Track separation | Batch and streaming separated with clear rationale; late-data reconciled via batch (Decision 4) | 20 |
| Idempotency & partitioning | Deterministic partitioned outputs; atomic/upsert writes; logical-date keying (Decision 1) | 15 |
| Schema & data quality | Validation gates between transforms; fail-fast before partial writes (Decision 2) | 15 |
| Backfill design | Bounded concurrency; logical-date tasks; explicit backfill path (Decision 3) | 10 |
| Observability & lineage | Freshness, latency, consumer lag, quality, lineage, cost — each with a signal/tool (Decision 5) | 15 |
| Capacity, cost & migration | Internally consistent cost estimate and a staged, shadow-then-cutover migration plan | 10 |

Review checklist (binary):

- [ ] Batch and streaming are in separate DAGs/services.
- [ ] No task uses `datetime.now()`; all key off the logical date.
- [ ] Every write is idempotent (partitioned path + atomic rename or upsert).
- [ ] A schema/quality gate exists between transforms and fails fast.
- [ ] Backfill concurrency is explicitly bounded.
- [ ] Lineage is emitted and freshness is alertable.
- [ ] Cost projection is internally consistent with stated rates.
- [ ] Migration path is staged (shadow → cutover → decommission).

## 5. Common mistakes

Drawn from the module-level grader notes
([SOLUTION.md](../SOLUTION.md)); each maps to a rubric dimension
above:

1. **Non-idempotent appends** — `df.to_csv(path, mode="a")` in a
   retried task quietly doubles data.
2. **`datetime.now()` inside tasks** — makes tasks
   non-deterministic and backfills produce wrong results.
3. **No partition design** — one flat output directory makes
   queries 10–100× slower than partitioned ones.
4. **DAGs with hundreds of tasks** — hard to schedule and slow to
   load; use TaskGroups or split into multiple DAGs.
5. **Missing pool/queue separation** — training jobs share a pool
   with light ETL and starve each other.
6. **No alerting on freshness** — a pipeline that silently stops
   running is the most common ML incident class.

Design-specific additions seen in submissions:

- Folding streaming late-arrival handling into the streaming
  pipeline instead of a separate batch reconciliation (violates
  Decision 4).
- Cost projections that are not internally consistent with the
  ingestion rates stated earlier in the same design.

## 6. References

Local exercise context:

- Learning exercise README —
  <https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-01-pipeline-architecture-design/README.md>
- Module rationale — [`../SOLUTION.md`](../SOLUTION.md)
- Worked reference design — [`./DESIGN.md`](./DESIGN.md)
- Bounded-concurrency backfiller — module exercise-09
  ([`../exercise-09-backfill-strategies`](../exercise-09-backfill-strategies))

Official project / standard documentation (tools named in the
design):

- Apache Airflow — <https://airflow.apache.org/docs/>
- Apache Flink — <https://nightlies.apache.org/flink/flink-docs-stable/>
- Apache Spark Structured Streaming —
  <https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html>
- dbt — <https://docs.getdbt.com/>
- Apache Kafka / Schema Registry —
  <https://kafka.apache.org/documentation/>
- Great Expectations — <https://docs.greatexpectations.io/>
- OpenLineage / Marquez — <https://openlineage.io/docs/>
- NIST AI Risk Management Framework (data governance, provenance,
  and measurement context for the lineage/quality decisions) —
  <https://www.nist.gov/itl/ai-risk-management-framework>
