"""Cross-encoder reranker."""
from __future__ import annotations

from sentence_transformers import CrossEncoder

from retrieve import Doc


_reranker = None


def rerank(query: str, candidates: list[Doc], top_k: int = 5) -> list[Doc]:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    pairs = [(query, c.text) for c in candidates]
    scores = _reranker.predict(pairs)
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return [Doc(id=d.id, text=d.text, score=float(s)) for d, s in ranked[:top_k]]
