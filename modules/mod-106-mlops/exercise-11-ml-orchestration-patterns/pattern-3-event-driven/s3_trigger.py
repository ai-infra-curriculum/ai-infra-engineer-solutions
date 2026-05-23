"""S3 PutObject event → SQS → Lambda → trigger Airflow DAG.

Lambda handler (deploy as lambda zip):
"""
import json
import os
from urllib import request


AIRFLOW_API = os.environ["AIRFLOW_API"]    # e.g., https://airflow.internal/api/v1
AUTH = os.environ["AIRFLOW_AUTH"]           # basic auth or token


def lambda_handler(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])
        for s3rec in body.get("Records", []):
            key = s3rec["s3"]["object"]["key"]
            if key.startswith("raw/iris/") and key.endswith(".parquet"):
                trigger_dag("train_iris", {"input_key": key})


def trigger_dag(dag_id: str, conf: dict):
    req = request.Request(
        f"{AIRFLOW_API}/dags/{dag_id}/dagRuns",
        data=json.dumps({"conf": conf}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {AUTH}"},
    )
    request.urlopen(req).read()
