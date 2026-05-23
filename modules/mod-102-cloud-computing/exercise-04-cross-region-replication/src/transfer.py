"""Per-object replication: atomic, integrity-verified, rate-limited."""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .backends import StorageBackend
from .limits import TokenBucket
from .manifest import Manifest, ObjectRecord


log = logging.getLogger(__name__)


@dataclass
class TransferResult:
    key: str
    bytes: int
    sha256: str
    dst_etag: str


def replicate_one(src: StorageBackend, dst: StorageBackend, key: str,
                   bucket: TokenBucket | None) -> TransferResult:
    meta = src.head(key)
    if meta is None:
        raise FileNotFoundError(f"source object missing: {key}")

    tmp = f".tmp-replication/{uuid.uuid4().hex}/{key}"
    sha = hashlib.sha256()
    bytes_transferred = 0

    def throttled_stream():
        nonlocal bytes_transferred
        for chunk in src.get_stream(key):
            sha.update(chunk)
            if bucket is not None:
                bucket.consume(len(chunk))
            bytes_transferred += len(chunk)
            yield chunk

    dst.put_stream(tmp, throttled_stream(), meta.size)
    dst.rename(tmp, key)
    dst_etag = dst.head(key).etag    # type: ignore[union-attr]
    return TransferResult(key=key, bytes=bytes_transferred, sha256=sha.hexdigest(), dst_etag=dst_etag)


def diff(src: StorageBackend, dst: StorageBackend, manifest: Manifest) -> dict[str, list[str]]:
    """Return {'new':[...], 'updated':[...], 'unchanged':[...]} for keys in src."""
    new, updated, unchanged = [], [], []
    for obj in src.list():
        rec = manifest.get(obj.key)
        if rec is None:
            new.append(obj.key)
        elif rec.src_etag != obj.etag:
            updated.append(obj.key)
        else:
            unchanged.append(obj.key)
    return {"new": new, "updated": updated, "unchanged": unchanged}


def replicate_many(src: StorageBackend, dst: StorageBackend, keys: list[str],
                    manifest: Manifest, *, concurrency: int = 4,
                    rate_mbps: float | None = None) -> dict[str, int]:
    bucket = TokenBucket(rate_mbps * 1_000_000 / 8) if rate_mbps else None

    def task(k: str) -> TransferResult:
        return replicate_one(src, dst, k, bucket)

    total_bytes, errors = 0, []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(task, k): k for k in keys}
        for fut in as_completed(futures):
            k = futures[fut]
            try:
                r = fut.result()
                total_bytes += r.bytes
                src_meta = src.head(k)
                manifest.upsert(ObjectRecord(
                    key=k, src_etag=src_meta.etag, src_size=src_meta.size,
                    dst_etag=r.dst_etag, sha256=r.sha256, last_synced_at=time.time(),
                ))
                log.info("replicated %s (%s bytes)", k, r.bytes)
            except Exception as exc:
                log.exception("failed %s", k)
                errors.append(k)

    return {"transferred": len(keys) - len(errors), "failed": len(errors), "bytes": total_bytes}


def verify_all(dst: StorageBackend, manifest: Manifest) -> list[str]:
    """Re-stream every destination object; report keys with checksum mismatch."""
    bad = []
    for key in manifest.all_keys():
        rec = manifest.get(key)
        if rec is None: continue
        sha = hashlib.sha256()
        for chunk in dst.get_stream(key):
            sha.update(chunk)
        if sha.hexdigest() != rec.sha256:
            log.error("checksum mismatch %s", key)
            bad.append(key)
    return bad
