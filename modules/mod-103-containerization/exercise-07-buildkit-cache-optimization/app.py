"""Smoke test: model loads from prefetched cache."""
from transformers import AutoModel
m = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
print("loaded:", m.__class__.__name__)
