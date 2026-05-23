"""Per-model serving cost from Prometheus + per-replica cost."""
from __future__ import annotations

import json

import httpx


PROM = "http://prometheus:9090"
COST_PER_POD_HOUR = 0.05


def query(promql: str) -> dict:
    return httpx.get(f"{PROM}/api/v1/query", params={"query": promql}).json()


def main():
    # Sum pod-hours by model_name over last 24h
    promql = (
        '(sum_over_time(count by (model_name) '
        '(up{model_name!=""})[24h:1m])) * 60 / 3600'
    )
    result = query(promql)["data"]["result"]
    cost = {r["metric"]["model_name"]: float(r["value"][1]) * COST_PER_POD_HOUR for r in result}
    print(json.dumps(cost, indent=2))


if __name__ == "__main__":
    main()
