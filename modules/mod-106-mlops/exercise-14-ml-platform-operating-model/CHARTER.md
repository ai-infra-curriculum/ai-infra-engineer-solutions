# ML Platform Team Charter

## Mission
Make it easy and safe for data scientists and product engineers to ship and operate ML in production. We do this by providing self-service infrastructure, opinionated workflows, and operational support — not by being a gatekeeper that every project must route through.

## What we own
- **Tracking + registry**: MLflow tracking server, model registry, retention.
- **Feature store**: Feast deployment, online + offline stores, materialization jobs.
- **Serving runtime**: standardized serving container, autoscaling, monitoring template.
- **Pipeline framework**: Airflow deployment + DAG templates + on-call.
- **Drift + bias monitoring**: dashboards + alert routing.
- **CI/CD plumbing**: GitHub Actions templates for ML workflows.
- **Cost attribution + budgets**: per-team and per-model rollups.

## What we explicitly DO NOT own
- Model architecture or hyperparameter choices (data scientists).
- Business metric definitions (product + analytics).
- Feature semantics / data correctness (data engineering + product).
- Quarterly model retraining schedules (model owners).

We provide the rails; teams drive the trains.

## Intake process

Three lanes:

1. **Self-serve** (60% of cases): teams use existing templates + docs, file zero tickets.
2. **Office hours** (30%): weekly 1hr drop-in; small unblockers.
3. **Project intake** (10%): >2-week effort that requires platform changes; ~6-week SLA.

## Support model

- **Tier 1 (on-call)**: 24/7 paging for platform outages (registry down, serving infra down). 30-min response, 4-hr restoration target.
- **Tier 2 (working hours)**: Slack channel monitored 9-6 local; non-blocking issues; same-day response.
- **Tier 3 (project queue)**: feature requests + improvements. Quarterly planning.

## On-call

- 4 engineers in rotation, 1-week shifts.
- Primary handles pages + Slack escalations; secondary handles non-blocking issues.
- Runbooks for every alert that has fired in the last 6 months (auto-required).
- Postmortem within 1 week of any SEV2+ incident.

## Success metrics

| Metric | Target |
|---|---|
| % new models using platform templates | > 80% |
| Median time from "trained" to "in prod" (using platform) | < 1 week |
| MTBF for serving infrastructure | > 30 days |
| MTTR for platform incidents | < 1 hour |
| Office hours utilization | > 50% slots filled weekly |
| Self-serve adoption | grows ~5%/qtr |
| ML cost attribution coverage | 100% of prod models tagged |

## Failure modes to avoid

- **Gatekeeper trap**: every model goes through a platform ticket. Avoided by making self-serve actually easy.
- **Custom-everywhere**: each team builds their own workaround. Avoided by being the obvious-best default.
- **Slow batching**: 6-month roadmap with no quick wins. Avoided by reserving 20% of capacity for short asks.

## Cadence

- Weekly: standup, on-call handoff, office hours.
- Bi-weekly: roadmap review with adjacent leads.
- Monthly: customer (data scientist + product eng) feedback meeting.
- Quarterly: charter review + metrics review with org leadership.
