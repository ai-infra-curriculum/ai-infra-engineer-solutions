"""Prefetch model weights into the HF cache during build (uses HF_TOKEN secret)."""
import os
import sys

from huggingface_hub import snapshot_download

token = os.environ.get("HF_TOKEN")
try:
    snapshot_download("sentence-transformers/all-MiniLM-L6-v2", token=token)
    print("weights prefetched into HF cache")
except Exception as exc:  # noqa: BLE001 — build smoke must not fail on registry hiccups
    # Public-model fetch can flake in offline CI; the cache mount survives across
    # rebuilds, so a single miss is non-fatal — the runtime stage still copies
    # whatever the cache holds and falls back to a fresh download at startup.
    print(f"warmup skipped: {exc}", file=sys.stderr)
