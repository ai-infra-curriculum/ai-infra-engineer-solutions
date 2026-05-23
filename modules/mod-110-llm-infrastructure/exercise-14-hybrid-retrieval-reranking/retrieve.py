"""Hybrid retrieval: BM25 + dense vectors, fused with reciprocal rank fusion."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Doc:
    id: str
    text: str
    score: float


def rrf_fuse(rankings: list[list[Doc]], k: int = 60) -> list[Doc]:
    """Reciprocal Rank Fusion — robust no-tuning fusion."""
    scores: dict[str, float] = defaultdict(float)
    docs: dict[str, Doc] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc.id] += 1 / (k + rank)
            docs[doc.id] = doc
    out = [docs[id] for id in sorted(scores, key=scores.get, reverse=True)]
    return out


def bm25_search(query: str, corpus_path: str, k: int = 30) -> list[Doc]:
    """BM25 via rank_bm25 lib."""
    from rank_bm25 import BM25Okapi
    docs = [line.strip().split("\t", 1) for line in open(corpus_path) if "\t" in line]
    tokenized = [d[1].split() for d in docs]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(query.split())
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [Doc(id=docs[i][0], text=docs[i][1], score=float(scores[i])) for i in top_idx]


def dense_search(query: str, qdrant_url: str = "http://localhost:6333",
                  collection: str = "docs", k: int = 30) -> list[Doc]:
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    c = QdrantClient(url=qdrant_url)
    emb = enc.encode(query).tolist()
    hits = c.search(collection, query_vector=emb, limit=k)
    return [Doc(id=str(h.id), text=h.payload["text"], score=h.score) for h in hits]


def hybrid_search(query: str, corpus_path: str, k: int = 10) -> list[Doc]:
    bm = bm25_search(query, corpus_path, k=30)
    dense = dense_search(query, k=30)
    fused = rrf_fuse([bm, dense])
    return fused[:k]
