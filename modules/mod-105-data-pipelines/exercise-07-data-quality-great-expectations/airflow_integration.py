"""Airflow task: run GE checkpoint; failure blocks downstream training."""
from __future__ import annotations

from airflow.decorators import task
from airflow.exceptions import AirflowFailException


@task
def run_quality_gate() -> dict:
    from great_expectations.data_context import DataContext
    ctx = DataContext()
    result = ctx.run_checkpoint(checkpoint_name="training_data")
    if not result["success"]:
        raise AirflowFailException(
            f"GE checkpoint failed; see data docs: "
            f"https://datadocs.example.com/training_data/{result['run_id'].run_name}"
        )
    return {"run_id": str(result["run_id"]), "stats": result["run_results"]}
