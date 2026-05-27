"""
Hybrid Retriever + Cross-encoder Re-ranker + RAG Benchmarking

Combines dense vector retrieval (via VectorStore) with a lightweight
BM25-style keyword scorer for hybrid retrieval, then optionally
re-ranks the merged candidate set with a cheap cross-encoder
heuristic (overlapping unigrams + bigrams between query and chunk).
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .embeddings import Chunk, Embedder, _tokenize, cosine_similarity
from .vector_store import SearchHit, VectorStore


logger = logging.getLogger(__name__)


# -- Retrieval results --------------------------------------------------


@dataclass
class RetrievalHit:
    """One hit through the hybrid retrieval pipeline."""

    chunk: Chunk
    dense_score: float
    keyword_score: float
    reranker_score: float
    combined_score: float


# -- BM25-style keyword scorer ------------------------------------------


class BM25Scorer:
    """Compact BM25 scorer over a chunk corpus."""

    K1 = 1.5
    B = 0.75

    def __init__(self, chunks: Sequence[Chunk]):
        self.chunks = list(chunks)
        self._doc_tokens: List[List[str]] = [_tokenize(c.text) for c in self.chunks]
        self._doc_lengths: List[int] = [len(t) for t in self._doc_tokens]
        if self.chunks:
            self._avg_doc_length = sum(self._doc_lengths) / len(self._doc_lengths)
        else:
            self._avg_doc_length = 0.0
        self._df: Dict[str, int] = {}
        for tokens in self._doc_tokens:
            for token in set(tokens):
                self._df[token] = self._df.get(token, 0) + 1

    def score(self, query: str) -> Dict[str, float]:
        """Score every chunk against the query; returns chunk_id -> score."""
        query_tokens = _tokenize(query)
        n = max(1, len(self.chunks))
        results: Dict[str, float] = {}
        for chunk, tokens, length in zip(self.chunks, self._doc_tokens, self._doc_lengths):
            score = 0.0
            tf_counts = Counter(tokens)
            for q in query_tokens:
                df = self._df.get(q, 0)
                if df == 0:
                    continue
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
                tf = tf_counts[q]
                denom = tf + self.K1 * (
                    1 - self.B + self.B * (length / max(1.0, self._avg_doc_length))
                )
                score += idf * (tf * (self.K1 + 1)) / max(denom, 1e-9)
            results[chunk.chunk_id] = score
        return results


# -- Cross-encoder-style re-ranker --------------------------------------


def rerank_score(query: str, chunk_text: str) -> float:
    """Cheap cross-encoder heuristic: weighted token + bigram overlap."""
    q_tokens = _tokenize(query)
    c_tokens = _tokenize(chunk_text)
    if not q_tokens or not c_tokens:
        return 0.0
    q_set = set(q_tokens)
    c_set = set(c_tokens)
    overlap = q_set & c_set
    unigram_score = len(overlap) / len(q_set)

    q_bigrams = {f"{a}_{b}" for a, b in zip(q_tokens, q_tokens[1:])}
    c_bigrams = {f"{a}_{b}" for a, b in zip(c_tokens, c_tokens[1:])}
    if q_bigrams and c_bigrams:
        bigram_overlap = len(q_bigrams & c_bigrams) / max(1, len(q_bigrams))
    else:
        bigram_overlap = 0.0
    return round(unigram_score * 0.6 + bigram_overlap * 0.4, 4)


# -- Hybrid retriever ---------------------------------------------------


@dataclass
class HybridRetrievalConfig:
    """Knobs for hybrid retrieval."""

    dense_weight: float = 0.5
    keyword_weight: float = 0.3
    rerank_weight: float = 0.2
    candidate_pool_size: int = 20
    enable_rerank: bool = True


class HybridRetriever:
    """Dense + BM25 + optional cross-encoder retrieval."""

    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        chunks: Sequence[Chunk],
        config: Optional[HybridRetrievalConfig] = None,
    ):
        self.store = store
        self.embedder = embedder
        self.bm25 = BM25Scorer(chunks)
        self.config = config or HybridRetrievalConfig()

    def retrieve(self, query: str, *, k: int = 5,
                 where: Optional[Dict[str, str]] = None) -> List[RetrievalHit]:
        query_embedding = self.embedder.embed(query)
        dense_hits = self.store.search(
            query_embedding, k=self.config.candidate_pool_size, where=where,
        )
        bm25_scores = self.bm25.score(query)

        # Normalize each score set to [0, 1] independently so the
        # weighted combination isn't dominated by either source.
        max_dense = max((h.score for h in dense_hits), default=1.0) or 1.0
        max_bm25 = max(bm25_scores.values(), default=1.0) or 1.0

        merged: List[RetrievalHit] = []
        for hit in dense_hits:
            bm25_raw = bm25_scores.get(hit.chunk.chunk_id, 0.0)
            dense_norm = hit.score / max_dense
            keyword_norm = bm25_raw / max_bm25 if max_bm25 > 0 else 0.0
            rerank = (
                rerank_score(query, hit.chunk.text)
                if self.config.enable_rerank else 0.0
            )
            combined = (
                self.config.dense_weight * dense_norm
                + self.config.keyword_weight * keyword_norm
                + self.config.rerank_weight * rerank
            )
            merged.append(RetrievalHit(
                chunk=hit.chunk,
                dense_score=round(hit.score, 4),
                keyword_score=round(bm25_raw, 4),
                reranker_score=rerank,
                combined_score=round(combined, 4),
            ))
        merged.sort(key=lambda h: h.combined_score, reverse=True)
        return merged[:k]


# -- RAG retrieval benchmarking ----------------------------------------


@dataclass(frozen=True)
class BenchmarkCase:
    """One labeled retrieval benchmark example."""

    query: str
    relevant_chunk_ids: List[str]


@dataclass
class BenchmarkReport:
    """Hit@K + MRR + per-query breakdown."""

    hit_at_k: float
    mean_reciprocal_rank: float
    average_recall_at_k: float
    per_query: List[Dict[str, object]]


def benchmark_retrieval(
    retriever: HybridRetriever,
    cases: List[BenchmarkCase],
    *,
    k: int = 5,
) -> BenchmarkReport:
    """Compute Hit@k + MRR + average Recall@k for a labelled query set."""
    if not cases:
        return BenchmarkReport(0.0, 0.0, 0.0, [])
    hits = 0
    mrr_total = 0.0
    recall_total = 0.0
    per_query: List[Dict[str, object]] = []
    for case in cases:
        results = retriever.retrieve(case.query, k=k)
        result_ids = [r.chunk.chunk_id for r in results]
        relevant = set(case.relevant_chunk_ids)
        is_hit = any(rid in relevant for rid in result_ids)
        if is_hit:
            hits += 1
            first_rank = next(
                (i + 1 for i, rid in enumerate(result_ids) if rid in relevant), 0,
            )
            mrr_total += 1.0 / first_rank
        recall = (
            len(set(result_ids) & relevant) / len(relevant) if relevant else 0.0
        )
        recall_total += recall
        per_query.append({
            "query": case.query,
            "hit": is_hit,
            "recall_at_k": round(recall, 4),
            "top_chunks": result_ids[:3],
        })
    return BenchmarkReport(
        hit_at_k=round(hits / len(cases), 4),
        mean_reciprocal_rank=round(mrr_total / len(cases), 4),
        average_recall_at_k=round(recall_total / len(cases), 4),
        per_query=per_query,
    )
