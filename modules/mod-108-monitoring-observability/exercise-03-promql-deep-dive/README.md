# PromQL Deep Dive — Solution

Reference for [learning exercise-03](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-03-promql-deep-dive/README.md).

- `PROMQL_CHEATSHEET.md` — all 25 worked queries with annotations.
- `recording-rules.yml` — Prometheus recording rules referenced by queries 18-19.

Load the recording rules with kube-prometheus-stack:

```bash
kubectl create configmap promql-recording-rules \
  --from-file=recording-rules.yml -n monitoring \
  --dry-run=client -o yaml | kubectl apply -f -
# Reference the ConfigMap in the Prometheus CRD additionalScrapeConfigs/ruleSelector
```
