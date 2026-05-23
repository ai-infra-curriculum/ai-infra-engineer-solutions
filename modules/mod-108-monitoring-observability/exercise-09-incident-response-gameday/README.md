# Incident Response Game Day — Solution

Reference for [learning exercise-09](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-108-monitoring-observability/exercises/exercise-09-incident-response-gameday/README.md).

Three injectable incidents + postmortem template + scoreboard CSV.

## Layout

```
exercise-09-incident-response-gameday/
├── README.md
├── injections/
│   ├── A-latency-regression.sh
│   ├── B-cascading-failure.sh
│   └── C-resource-exhaustion.sh
├── revert/
│   └── revert-all.sh
├── POSTMORTEM_TEMPLATE.md
└── scoreboard.csv
```

## Workflow

```bash
./injections/A-latency-regression.sh    # inject
# wait, observe alerts, diagnose
./revert/revert-all.sh                    # revert
# fill out POSTMORTEM_TEMPLATE.md + add row to scoreboard.csv
```
