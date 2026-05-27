# SOLUTION — Monitoring and Observability

> Read this *after* you have wired up the reference monitoring
> stack. This document explains *why* the architecture is shaped
> the way it is and how to think about ML-specific observability
> concerns that general SRE practice doesn't cover.

## What this module is really teaching

Generic application observability is a solved problem in 2026:
Prometheus + Grafana + OpenTelemetry + a logging backend cover
the territory. ML observability adds three concerns that don't
exist in normal apps:

1. **Model performance metrics** — accuracy, precision, recall —
   that need ground truth to compute, often arriving days later.
2. **Drift detection** — both data drift (input distribution
   change) and concept drift (model-correctness degradation over
   time).
3. **Per-segment fairness** — performance across protected
   attributes that aggregates well but matters at the bucket
   level.

The reference solutions integrate these concerns into the same
observability stack, rather than treating ML metrics as a
separate world.

## Architectural decisions and *why*

### Decision 1: Prometheus pull model, not push-based metrics

The reference uses Prometheus scraping for application metrics.
The reason: pull-based scraping aligns better with Kubernetes
service discovery (Prometheus discovers pods via the K8s API and
scrapes them automatically). Push-based systems (StatsD, OpenTSDB
push) require explicit push targets that move when pods do.

For batch workloads where pull doesn't fit, the reference uses
the **PushGateway** as the deliberate exception.

### Decision 2: One dashboard per model, not a "ML dashboard"

The reference Grafana setup creates one dashboard per registered
model. The reason: a single mega-dashboard becomes useless past 3
models — the panels are too small, and engineers ignore them.
Per-model dashboards stay focused.

### Decision 3: Burn-rate alerts over static thresholds

Alerting rules use SLO-aligned burn rates:

- Page if error budget burns at >10x normal for 5 minutes.
- Notify if burn rate >2x normal for 1 hour.
- Don't page on raw error count.

The reason: static thresholds either page constantly during
traffic spikes or never page during low-traffic outages. Burn
rates normalize against expected traffic.

### Decision 4: Three drift detectors, three signals

Drift detection in mod-108 ex-02 emits three separate metrics:

- **Data drift**: KS test p-value over a rolling window. Catches
  input-distribution shifts.
- **Concept drift**: rolling-window accuracy. Catches model-
  performance degradation regardless of input.
- **Prediction drift**: chi-square test on output distribution.
  Catches "model is suddenly predicting all positives" failures.

All three live in Prometheus; alerting fires on each
independently. They detect different failures and conflating them
hides the signal.

### Decision 5: Structured JSON logging at the source

Reference applications emit logs as JSON, not as text. The
reason: log aggregators (Loki, ELK, CloudWatch Logs Insights)
parse JSON natively; parsing free-text logs is fragile and slow.
The cost is 15 lines of logging config; the benefit is the
ability to query logs by field.

### Decision 6: Trace sampling at the boundary, propagation through

The reference enables OpenTelemetry trace propagation through
every service hop but samples at the edge (1-10% of requests).
The reason: 100% sampling produces too much data to store; 0%
sampling produces no diagnostic value. Boundary-based sampling
keeps storage bounded and still captures every microservice hop
within a sampled trace.

## Trade-offs we deliberately accepted

### Prometheus + Grafana over Datadog / New Relic

The reference uses the OSS stack. Commercial APMs are richer but
the curriculum bias is toward primitives engineers can reason
about. The patterns transfer to commercial tools.

### Loki for logs, not ELK

Loki indexes log labels but not log content. The reason: it's
much cheaper to operate at scale (10-100x lower storage cost)
than ELK. The trade-off: full-text search across log content is
slower; for ML observability that's usually fine because the
queries are mostly label-based.

### No tracing in the introductory exercises

OpenTelemetry traces don't show up until ex-04. The reason:
metrics and logs cover 90% of ML observability needs; traces are
critical when you have many services calling each other (LLM
serving, RAG pipelines) but overkill for a simple ML API.

## Common mistakes graders see

1. **Cardinality explosion**: using user IDs or request IDs as
   label values on Prometheus metrics blows up cardinality and
   eventually OOMs Prometheus itself.
2. **Alert fatigue**: every PR adds an alert; six months later
   nobody pays attention to the channel. Curate aggressively.
3. **No runbook links in alerts**: the on-call engineer wakes
   up, sees the alert, and has no idea what to do. Every alert
   should link to a runbook.
4. **Dashboards without time-range comparisons**: a 200ms p99 is
   meaningless without "vs. last week" context.
5. **Logging PII**: regulated workloads log user PII into
   Elasticsearch, which then needs to be scrubbed. Filter at the
   source.
6. **Metrics without help text**: the next engineer reading the
   metric has no idea what it measures.

## When to go beyond this implementation

- Adopt **synthetic monitoring** — synthetic prediction requests
  on a schedule catch regressions before users do.
- Add **distributed tracing context propagation** to background
  jobs (Airflow tasks, Celery workers) so end-to-end traces span
  async pipelines.
- Move to **eBPF-based observability** (Pixie, Parca) for low-
  overhead production-time profiling.

## Related curriculum touchpoints

- ``engineer/mod-104-kubernetes`` — observability is most useful
  when paired with Kubernetes events.
- ``engineer/mod-106-mlops`` — the model-lifecycle context for
  drift detection.
- ``ml-platform/mod-008-observability`` — the platform-level
  view of multi-tenant observability.
- ``junior-engineer/project-04-monitoring-alerting`` — the
  user-facing project these solutions support.
