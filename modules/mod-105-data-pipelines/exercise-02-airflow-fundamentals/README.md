# Airflow Fundamentals DAG — Solution

Reference for [learning exercise-02](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-02-airflow-fundamentals/README.md).

`recs_training_dag.py` ticks all 7 requirements:

| Requirement | Implementation |
|---|---|
| 6+ TaskFlow tasks | ingest_s3, validate, feature_engineer, train, evaluate, deploy, skip_deploy, gate |
| Conditional branching | `@task.branch` `quality_gate` + `deploy_gate` |
| Dynamic task mapping | `feature_engineer.partial(...).expand(category=CATEGORIES)` |
| XCom passing | path strings + report dict between tasks |
| Retries + backoff | `default_args` with exponential backoff |
| SLA + Slack | `sla=4h` + `sla_miss_callback` |
| Task groups | `@task_group validate_and_transform` |

```bash
cp recs_training_dag.py $AIRFLOW_HOME/dags/
airflow dags trigger recs_training
```
