"""Airflow DAG: recs training pipeline. TaskFlow API + branching + dynamic mapping."""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task, task_group
from airflow.exceptions import AirflowSkipException
from airflow.operators.python import get_current_context
from airflow.utils.trigger_rule import TriggerRule


DEFAULT_ARGS = {
    "owner": "ml-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "sla": timedelta(hours=4),
}

CATEGORIES = ["apparel", "electronics", "home", "books"]


def _notify_slack_sla(dag, task_list, blocking_task_list, slas, blocking_tis):
    """Posted to Slack when SLA is missed."""
    # In production, post to Slack via slack_webhook.
    print(f"SLA MISS for {dag.dag_id}: {[s.task_id for s in slas]}")


@dag(
    dag_id="recs_training",
    start_date=datetime(2026, 1, 1),
    schedule="0 4 * * *",
    catchup=False,
    default_args=DEFAULT_ARGS,
    sla_miss_callback=_notify_slack_sla,
    tags=["ml", "recs"],
)
def pipeline():
    @task
    def ingest_s3() -> str:
        return "s3://datalake/raw/recs/2026-05-22/"

    @task_group
    def validate_and_transform(raw_path: str):
        @task
        def validate(path: str) -> dict:
            # In real life: run GE checkpoint. Returns quality summary.
            return {"path": path, "row_count": 4_200_000, "pass": True}

        @task.branch
        def quality_gate(report: dict) -> str:
            return "validate_and_transform.feature_engineer" if report["pass"] else "skip_deploy"

        @task
        def feature_engineer(category: str, raw_path: str) -> str:
            return f"s3://datalake/features/{category}/2026-05-22/"

        report = validate(raw_path)
        gate = quality_gate(report)
        engineered = feature_engineer.partial(raw_path=raw_path).expand(category=CATEGORIES)
        report >> gate >> engineered
        return engineered

    @task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
    def train(feature_paths: list[str]) -> str:
        return f"s3://datalake/models/recs/2026-05-22/model.bin"

    @task
    def evaluate(model_path: str) -> dict:
        return {"model": model_path, "auc": 0.87, "pass": True}

    @task.branch
    def deploy_gate(eval_result: dict) -> str:
        return "deploy" if eval_result["pass"] else "skip_deploy"

    @task
    def deploy(model_path: str) -> str:
        return f"deployed:{model_path}"

    @task
    def skip_deploy():
        raise AirflowSkipException("quality or eval gate failed")

    raw = ingest_s3()
    features = validate_and_transform(raw)
    model = train(features)
    eval_result = evaluate(model)
    gate = deploy_gate(eval_result)
    gate >> [deploy(model), skip_deploy()]


pipeline()
