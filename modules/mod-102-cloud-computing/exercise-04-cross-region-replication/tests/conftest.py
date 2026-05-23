"""Spins up a Minio container for tests."""
import os
import sys
import time

import boto3
import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def minio_endpoint():
    """Assume Minio running at localhost:9000 (start via docker-compose in CI)."""
    yield "http://localhost:9000"


@pytest.fixture
def s3_client(minio_endpoint):
    return boto3.client(
        "s3", endpoint_url=minio_endpoint,
        aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin",
        region_name="us-east-1",
    )


@pytest.fixture
def buckets(s3_client):
    src, dst = "rep-src", "rep-dst"
    for b in (src, dst):
        try: s3_client.create_bucket(Bucket=b)
        except Exception: pass
    yield src, dst
    for b in (src, dst):
        objs = s3_client.list_objects_v2(Bucket=b).get("Contents", [])
        for o in objs: s3_client.delete_object(Bucket=b, Key=o["Key"])
