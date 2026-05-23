"""Prefetch model weights into the HF cache during build (uses HF_TOKEN secret)."""
import os
from huggingface_hub import snapshot_download

token = os.environ.get("HF_TOKEN")
snapshot_download("sentence-transformers/all-MiniLM-L6-v2", token=token)
print("weights prefetched into HF cache")
