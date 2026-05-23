"""Periodic exporter: per-dataset freshness + row count to Prometheus."""
from __future__ import annotations

import time
from datetime import UTC, datetime

import boto3
from prometheus_client import Gauge, start_http_server


FRESHNESS = Gauge(
    "dataset_freshness_seconds",
    "Seconds since dataset was last written",
    ["dataset"],
)
ROWS = Gauge("dataset_row_count", "Row count (approx)", ["dataset"])

DATASETS = {
    "events.recs_training_v1": "s3://datalake/curated/events.recs_training_v1/",
    "features.recs_v1": "s3://datalake/curated/features.recs_v1/",
    "models.recs": "s3://datalake/models/recs/latest/",
}


def s3_last_modified(uri: str) -> datetime | None:
    s3 = boto3.client("s3")
    bucket, _, prefix = uri.removeprefix("s3://").partition("/")
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
    objs = resp.get("Contents", [])
    if not objs:
        return None
    return max(o["LastModified"] for o in objs)


def main():
    start_http_server(9100)
    while True:
        now = datetime.now(UTC)
        for name, uri in DATASETS.items():
            lm = s3_last_modified(uri)
            if lm:
                FRESHNESS.labels(dataset=name).set((now - lm).total_seconds())
        time.sleep(60)


if __name__ == "__main__":
    main()
