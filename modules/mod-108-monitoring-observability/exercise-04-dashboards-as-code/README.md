# Grafana Dashboards as Code — Solution

Reference for [learning exercise-04](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-04-dashboards-as-code/README.md).

Python + grafanalib path. Three dashboards rendered to JSON + provisioned automatically.

## Layout

```
exercise-04-dashboards-as-code/
├── README.md, requirements.txt
├── dashboards/
│   ├── api_overview.dashboard.py
│   ├── ml_drift.dashboard.py
│   └── slo_budget.dashboard.py
├── render.py                   # render all → out/*.json
├── provisioning/
│   ├── datasources/prometheus.yaml
│   └── dashboards/iris.yaml
└── .github/workflows/dashboards.yml  # lint + render + PR comment
```

## Run

```bash
./scripts/setup.sh
python render.py                   # produces out/*.json
docker compose up -d grafana       # auto-loads from provisioning/
open http://localhost:3000
```
