# mlfinops — Per-Team Cloud Cost Attribution CLI — Solution

Reference solution for [learning exercise-08-finops-automation](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-102-cloud-computing/exercises/exercise-08-finops-automation/README.md).

A Python CLI that collects daily AWS Cost Explorer data, classifies by team/workload via tags, identifies idle resources, and emits a weekly digest to Slack.

## Layout

```
exercise-08-finops-automation/
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── collect.py
│   ├── idle.py
│   ├── report.py
│   └── slack.py
├── tests/
│   ├── conftest.py
│   └── test_collect.py
└── budgets.yaml
```

## Quick start

```bash
./scripts/setup.sh
mlfinops collect --date 2026-05-22
mlfinops idle --days 7
mlfinops report --week 2026-05-19
mlfinops digest --week 2026-05-19   # posts to Slack
```
