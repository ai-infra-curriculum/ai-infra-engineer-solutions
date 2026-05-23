"""Airflow DAG that invokes `dbt build`."""
from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator


@dag(dag_id="dbt_build", start_date=datetime(2026, 1, 1),
     schedule="0 5 * * *", catchup=False, tags=["dbt"])
def dbt_build():
    KubernetesPodOperator(
        task_id="dbt_build",
        name="dbt-build",
        image="ghcr.io/me/dbt-runner:1.7",
        cmds=["dbt"],
        arguments=["build", "--target", "prod", "--fail-fast"],
        env_vars={"DBT_PROFILES_DIR": "/etc/dbt"},
        image_pull_policy="Always",
    )


dbt_build()
