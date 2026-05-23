# Alertmanager Routing — Solution

Reference for [learning exercise-07](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-07-alertmanager-routing/README.md).

## Layout

```
exercise-07-alertmanager-routing/
├── README.md
├── alerts.yml             # 10 alert rules incl. multi-window burn-rate
├── alertmanager.yml       # routing tree + receivers + templates
├── inhibitions.yml        # inhibition + grouping config (loaded with alertmanager.yml)
└── scripts/
    ├── test-alerts.sh     # uses amtool to fire each severity
    └── silence.sh         # CLI walkthrough
```

## Test

```bash
amtool config check alertmanager.yml
amtool alert add alertname=HighErrorRate severity=critical
amtool silence add alertname=KnownNoisyAlert duration=2h
```
