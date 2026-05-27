"""
Vector Store

VectorStore Protocol + InMemoryVectorStore reference implementation.
The store accepts Chunks with embeddings and answers k-NN cosine
queries with optional metadata filtering (`where` clause).

In production a Qdrant / Weaviate / pgvector client would implement
the Protocol; the in-memory backend gives the curriculum a runnable
end-to-end pipeline.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Protocol

from .embeddings import Chunk, cosine_similarity


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    """One k-NN hit: the chunk + its similarity score."""

    chunk: Chunk
    score: float


class VectorStore(Protocol):
    """Pluggable vector store."""

    def upsert(self, chunks: List[Chunk]) -> int: ...

    def delete_document(self, doc_id: str) -> int: ...

    def search(
        self,
        query_embedding: List[float],
        *,
        k: int = 5,
        where: Optional[Dict[str, str]] = None,
    ) -> List[SearchHit]: ...

    def count(self) -> int: ...


class InMemoryVectorStore:
    """Thread-safe in-memory vector store with brute-force search."""

    def __init__(self) -> None:
        self._chunks: Dict[str, Chunk] = {}
        self._lock = threading.RLock()

    def upsert(self, chunks: List[Chunk]) -> int:
        upserted = 0
        with self._lock:
            for chunk in chunks:
                if not chunk.embedding:
                    raise ValueError(
                        f"Chunk {chunk.chunk_id} has no embedding; embed_chunks "
                        "must be called before upsert."
                    )
                self._chunks[chunk.chunk_id] = chunk
                upserted += 1
        return upserted

    def delete_document(self, doc_id: str) -> int:
        with self._lock:
            to_remove = [
                cid for cid, chunk in self._chunks.items()
                if chunk.doc_id == doc_id
            ]
            for cid in to_remove:
                self._chunks.pop(cid)
            return len(to_remove)

    def search(
        self,
        query_embedding: List[float],
        *,
        k: int = 5,
        where: Optional[Dict[str, str]] = None,
    ) -> List[SearchHit]:
        with self._lock:
            candidates = self._chunks.values()
            if where:
                candidates = [
                    c for c in candidates
                    if all(c.metadata.get(key) == value for key, value in where.items())
                ]
            scored = [
                SearchHit(chunk=c, score=cosine_similarity(query_embedding, c.embedding))
                for c in candidates
            ]
            scored.sort(key=lambda h: h.score, reverse=True)
            return scored[:k]

    def count(self) -> int:
        with self._lock:
            return len(self._chunks)

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
