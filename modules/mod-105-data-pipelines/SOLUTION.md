# SOLUTION — Data Pipelines

> Read this *after* you have built the reference pipelines
> yourself. This document explains *why* the data-pipeline
> architecture is shaped the way it is — what's batch vs. streaming,
> where idempotency matters, and how to avoid the data-pipeline
> debt that plagues most ML teams.

## What this module is really teaching

Data pipelines are where most ML projects accumulate quiet
technical debt:

- Schedules that drift, dependencies that aren't tracked.
- Schema changes that break downstream consumers months later.
- Backfills that take three days because nobody designed for them.
- "It worked yesterday" failures that nobody can diagnose because
  the pipeline doesn't log enough.

The reference solutions are opinionated about idempotency,
observability, and schema management because those are the
disciplines that distinguish stable pipelines from constant
firefighting.

## Architectural decisions and *why*

### Decision 1: Idempotent task design from the start

Every task in the reference DAGs is idempotent. If a task runs
twice with the same inputs, the output is identical. The reason:
Airflow (and every other orchestrator) **will** retry tasks; if
your tasks aren't idempotent, retries corrupt state.

Patterns we use:
- Writes go to a temporary location, then atomically renamed.
- Database upserts use ``INSERT ... ON CONFLICT`` (or ``MERGE``).
- File operations use deterministic output paths derived from the
  task's logical date / data partition.

**Anti-pattern to avoid**: ``df.to_csv("output.csv")`` from a task
without partition awareness — running twice doubles the data.

### Decision 2: Schema validation between every transform

Every transformation in the reference pipelines runs through a
schema check (Great Expectations or pandera). The reason: schema
drift in upstream sources silently corrupts downstream models.
The cost of catching schema changes at ingestion is small; the
cost of finding out three weeks later is enormous.

### Decision 3: Backfills as a first-class operation

DAG design assumes backfills will happen. Concrete moves:
- ``max_active_runs=N`` is set explicitly so a backfill doesn't
  blow up the cluster.
- Tasks reference ``{{ ds }}`` (the logical date), never
  ``datetime.now()``.
- Connection / pool limits are sized for backfill concurrency,
  not steady-state.

The reason: every ML team needs to backfill data at least once a
quarter (new feature, fixed bug, model retraining). Designing for
it ahead of time avoids the rewrite.

### Decision 4: Batch + streaming patterns separated cleanly

Streaming and batch live in separate DAGs / services. The reason:
they have completely different failure modes and operational
characteristics. Streaming alerts page the on-call; batch
failures are an email-by-9am affair. Mixing them in one codebase
causes ops confusion.

When you need late-arriving data on a streaming pipeline, the
right answer is a separate batch backfill DAG, not a hybrid
streaming-with-late-arrival-handling pipeline.

### Decision 5: Data lineage as code

The reference pipelines emit OpenLineage events as they run. The
reason: when a downstream model breaks, the team needs to answer
"what changed in the data?" Lineage gives that answer in seconds
instead of days.

## Trade-offs we deliberately accepted

### Airflow as the orchestrator default

The reference uses Airflow 2.x as the orchestrator. Prefect,
Dagster, Argo Workflows, and Temporal all have legitimate cases.
Airflow wins on documentation, integrations, and the size of the
talent pool. The patterns transfer to other orchestrators.

### Spark over Dask for heavy transforms

For 100GB+ transforms the reference uses Spark. Dask has nicer
Python ergonomics but Spark's tooling (catalog, Iceberg
integration, Delta Lake) is mature in ways Dask's isn't yet.

### Pandas tolerated for small transforms

Anything under ~5GB stays in pandas. Polars would arguably be
better but pandas is what your team's data scientists already
know. The migration tax isn't worth it for small data.

## Common mistakes graders see

1. **Non-idempotent appends**: ``df.to_csv(path, mode="a")`` in a
   retried task quietly doubles data.
2. **``datetime.now()`` inside tasks**: makes the task non-
   deterministic and backfills produce wrong results.
3. **No partition design**: writing everything to one flat
   directory makes queries 10-100x slower than partitioned ones.
4. **DAGs with hundreds of tasks**: hard to schedule, slow to
   load. Use TaskGroups or split into multiple DAGs.
5. **Missing pool / queue separation**: training jobs share a
   pool with light ETL and starve each other.
6. **No alerting on freshness**: a pipeline that silently stops
   running is the most common ML incident class.

## When to go beyond this implementation

- Adopt **Iceberg / Delta Lake** for ACID guarantees on data lake
  storage.
- Add a **feature store** (Feast / Tecton) so features generated
  by these pipelines are queryable at low latency.
- Migrate to **Dagster** when type-checked assets become more
  important than the established Airflow ecosystem.

## Related curriculum touchpoints

- ``engineer/mod-106-mlops`` — turning the data products into
  trained models.
- ``engineer/mod-108-monitoring-observability`` — observing
  pipeline health.
- ``ml-platform/mod-004-feature-store`` — the feature store that
  consumes pipeline outputs.
- ``junior-engineer/project-03-ml-pipeline-tracking`` — the
  end-to-end user-facing pipeline.
