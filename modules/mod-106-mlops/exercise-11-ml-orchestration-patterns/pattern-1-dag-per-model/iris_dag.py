"""Simple DAG-per-model. One file per model; easiest to read + debug."""
from datetime import datetime

from airflow.decorators import dag, task


@dag(dag_id="train_iris", start_date=datetime(2026, 1, 1), schedule="0 4 * * *", catchup=False)
def pipeline():
    @task
    def ingest() -> str: return "s3://datalake/iris.parquet"

    @task
    def train(p: str) -> str: return f"trained on {p}"

    @task
    def deploy(model: str) -> str: return f"deployed {model}"

    deploy(train(ingest()))


pipeline()
