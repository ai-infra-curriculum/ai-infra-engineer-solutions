# Per-Model Cost Attribution — Solution

Reference for [learning exercise-12](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-12-model-cost-attribution/README.md).

## Layout

```
exercise-12-model-cost-attribution/
├── README.md
├── tagging/labels.yaml             # required labels on every model resource
├── collect_training_cost.py         # GPU/CPU time × instance price
├── collect_serving_cost.py          # ServiceMonitor: requests × cost/req
├── budgets.yaml                     # per-model monthly budgets
└── dashboards/per-model-cost.json   # Grafana panel
```
