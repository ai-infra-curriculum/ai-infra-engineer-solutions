"""Single DAG generates one task per model from a YAML registry."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from airflow.decorators import dag, task


REGISTRY = yaml.safe_load((Path(__file__).parent / "models.yaml").read_text())


def make_dag(model_cfg: dict):
    @dag(
        dag_id=f"train_{model_cfg['name']}",
        start_date=datetime(2026, 1, 1),
        schedule=model_cfg.get("schedule", "0 4 * * *"),
        catchup=False,
        tags=["parametric", model_cfg["team"]],
    )
    def pipeline():
        @task
        def train(cfg=model_cfg) -> str:
            return f"trained {cfg['name']} on {cfg['dataset']}"
        train()
    return pipeline()


for cfg in REGISTRY["models"]:
    make_dag(cfg)
