"""Pull daily AWS Cost Explorer data, attribute by team tag."""
from __future__ import annotations

from datetime import date, timedelta

import boto3
import pandas as pd


def collect_daily(target_date: date) -> pd.DataFrame:
    ce = boto3.client("ce", region_name="us-east-1")
    start = target_date.isoformat()
    end = (target_date + timedelta(days=1)).isoformat()

    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[
            {"Type": "TAG", "Key": "team"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ],
    )

    rows = []
    for result_by_time in response.get("ResultsByTime", []):
        for group in result_by_time.get("Groups", []):
            team_key = group["Keys"][0]
            team = team_key.split("$")[-1] or "untagged"
            service = group["Keys"][1]
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
            rows.append({
                "date": target_date.isoformat(),
                "team": team,
                "service": service,
                "cost_usd": cost,
            })

    return pd.DataFrame(rows)


def upload_to_s3(df: pd.DataFrame, bucket: str, target_date: date) -> str:
    """Write daily parquet to s3://<bucket>/daily/<date>.parquet"""
    import io
    buf = io.BytesIO()
    df.to_parquet(buf)
    buf.seek(0)
    key = f"daily/{target_date.isoformat()}.parquet"
    boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
    return f"s3://{bucket}/{key}"
