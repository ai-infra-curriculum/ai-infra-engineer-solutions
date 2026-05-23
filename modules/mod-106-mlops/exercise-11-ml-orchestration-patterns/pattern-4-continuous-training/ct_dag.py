"""Continuous training: hourly retrain if drift > threshold OR data growth > X."""
from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.exceptions import AirflowSkipException


@dag(dag_id="continuous_training", start_date=datetime(2026, 1, 1),
     schedule="0 * * * *", catchup=False, tags=["ct"])
def ct():
    @task
    def check_drift() -> dict:
        # Real impl: query Prometheus / drift system
        psi = 0.18
        new_rows = 1_200_000
        return {"psi": psi, "new_rows": new_rows}

    @task.branch
    def gate(state: dict) -> str:
        if state["psi"] > 0.25 or state["new_rows"] > 1_000_000:
            return "retrain"
        return "skip"

    @task
    def retrain():
        print("training new model")

    @task
    def skip():
        raise AirflowSkipException("no retrain needed this hour")

    s = check_drift()
    g = gate(s)
    g >> [retrain(), skip()]


ct()
