"""Storage backend abstraction. Only S3 implemented; structure ready for GCS/Azure."""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Iterator, Protocol


@dataclass(frozen=True)
class ObjectMeta:
    key: str
    size: int
    etag: str


class StorageBackend(Protocol):
    def list(self, prefix: str = "") -> Iterator[ObjectMeta]: ...
    def head(self, key: str) -> ObjectMeta | None: ...
    def get_stream(self, key: str, chunk_size: int = 1 << 20) -> Iterator[bytes]: ...
    def put_stream(self, key: str, stream: Iterator[bytes], size: int) -> str: ...
    def rename(self, src: str, dst: str) -> None: ...
    def delete(self, key: str) -> None: ...


class S3Backend:
    def __init__(self, bucket: str, prefix: str = "", *, endpoint_url: str | None = None,
                 region: str = "us-east-1") -> None:
        import boto3
        self.client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""

    def _key(self, k: str) -> str:
        return self.prefix + k

    def list(self, prefix: str = "") -> Iterator[ObjectMeta]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._key(prefix)):
            for obj in page.get("Contents", []):
                key = obj["Key"][len(self.prefix):]
                yield ObjectMeta(key=key, size=obj["Size"], etag=obj["ETag"].strip('"'))

    def head(self, key: str) -> ObjectMeta | None:
        try:
            r = self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        except self.client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            raise
        return ObjectMeta(key=key, size=r["ContentLength"], etag=r["ETag"].strip('"'))

    def get_stream(self, key: str, chunk_size: int = 1 << 20) -> Iterator[bytes]:
        r = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        body = r["Body"]
        while chunk := body.read(chunk_size):
            yield chunk

    def put_stream(self, key: str, stream: Iterator[bytes], size: int) -> str:
        buf = io.BytesIO(b"".join(stream))
        r = self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=buf)
        return r["ETag"].strip('"')

    def rename(self, src: str, dst: str) -> None:
        self.client.copy_object(
            Bucket=self.bucket, Key=self._key(dst),
            CopySource={"Bucket": self.bucket, "Key": self._key(src)},
        )
        self.delete(src)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))


def parse_uri(uri: str) -> tuple[str, str, str]:
    """s3://bucket/some/prefix → (s3, bucket, some/prefix)."""
    scheme, _, rest = uri.partition("://")
    bucket, _, prefix = rest.partition("/")
    return scheme, bucket, prefix
