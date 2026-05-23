"""Embedding-based semantic cache."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer


DIM = 384
SIMILARITY_THRESHOLD = 0.92      # cosine; tune per workload


@dataclass
class CacheHit:
    response: str
    score: float
    age_seconds: float


class SemanticCache:
    def __init__(self, qdrant_url: str = "http://localhost:6333",
                 collection: str = "llm-cache"):
        self.client = QdrantClient(url=qdrant_url)
        self.encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        try:
            self.client.get_collection(collection)
        except Exception:
            self.client.create_collection(
                collection,
                vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
            )
        self.collection = collection

    def get(self, prompt: str) -> CacheHit | None:
        emb = self.encoder.encode(prompt).tolist()
        results = self.client.search(self.collection, query_vector=emb, limit=1)
        if not results:
            return None
        top = results[0]
        if top.score < SIMILARITY_THRESHOLD:
            return None
        return CacheHit(
            response=top.payload["response"],
            score=top.score,
            age_seconds=time.time() - top.payload["ts"],
        )

    def put(self, prompt: str, response: str):
        emb = self.encoder.encode(prompt).tolist()
        point_id = int(hashlib.md5(prompt.encode()).hexdigest()[:15], 16)
        self.client.upsert(
            self.collection,
            points=[PointStruct(
                id=point_id, vector=emb,
                payload={"prompt": prompt, "response": response, "ts": time.time()},
            )],
        )
