"""End-to-end replication tests against Minio."""
import os

import pytest

os.environ.setdefault("AWS_ACCESS_KEY_ID", "minioadmin")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "minioadmin")

from src.backends import S3Backend  # noqa: E402
from src.manifest import Manifest  # noqa: E402
from src.transfer import diff, replicate_many, verify_all  # noqa: E402


def test_diff_classifies_new_and_unchanged(tmp_path, s3_client, buckets):
    src_b, dst_b = buckets
    s3_client.put_object(Bucket=src_b, Key="a.txt", Body=b"hello")
    s3_client.put_object(Bucket=src_b, Key="b.txt", Body=b"world")

    src = S3Backend(bucket=src_b, endpoint_url="http://localhost:9000")
    dst = S3Backend(bucket=dst_b, endpoint_url="http://localhost:9000")
    m = Manifest(tmp_path / "m.db")

    report = diff(src, dst, m)
    assert sorted(report["new"]) == ["a.txt", "b.txt"]
    assert report["unchanged"] == []


def test_replicate_copies_and_verifies(tmp_path, s3_client, buckets):
    src_b, dst_b = buckets
    s3_client.put_object(Bucket=src_b, Key="a.txt", Body=b"hello")

    src = S3Backend(bucket=src_b, endpoint_url="http://localhost:9000")
    dst = S3Backend(bucket=dst_b, endpoint_url="http://localhost:9000")
    m = Manifest(tmp_path / "m.db")

    result = replicate_many(src, dst, ["a.txt"], m, concurrency=1, rate_mbps=None)
    assert result["transferred"] == 1
    assert result["failed"] == 0

    body = s3_client.get_object(Bucket=dst_b, Key="a.txt")["Body"].read()
    assert body == b"hello"

    assert verify_all(dst, m) == []


def test_idempotent(tmp_path, s3_client, buckets):
    src_b, dst_b = buckets
    s3_client.put_object(Bucket=src_b, Key="a.txt", Body=b"hello")

    src = S3Backend(bucket=src_b, endpoint_url="http://localhost:9000")
    dst = S3Backend(bucket=dst_b, endpoint_url="http://localhost:9000")
    m = Manifest(tmp_path / "m.db")

    replicate_many(src, dst, ["a.txt"], m, concurrency=1)
    # second pass: nothing new
    report = diff(src, dst, m)
    assert report["new"] == []
    assert report["unchanged"] == ["a.txt"]


def test_resume_after_partial(tmp_path, s3_client, buckets):
    src_b, dst_b = buckets
    s3_client.put_object(Bucket=src_b, Key="a.txt", Body=b"hello")
    s3_client.put_object(Bucket=src_b, Key="b.txt", Body=b"world")

    src = S3Backend(bucket=src_b, endpoint_url="http://localhost:9000")
    dst = S3Backend(bucket=dst_b, endpoint_url="http://localhost:9000")
    m = Manifest(tmp_path / "m.db")

    # simulate partial: replicate only a.txt
    replicate_many(src, dst, ["a.txt"], m, concurrency=1)

    report = diff(src, dst, m)
    assert report["new"] == ["b.txt"]
    assert report["unchanged"] == ["a.txt"]
