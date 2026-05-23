# RAG Retrieval Quality Improvement

Measured on a 500-question internal QA dataset against a 100K-doc corpus.

| Method | recall@5 | nDCG@5 | latency p95 |
|---|---|---|---|
| Dense only | 0.71 | 0.62 | 35ms |
| Hybrid (BM25 + dense, RRF) | 0.84 | 0.74 | 60ms |
| Hybrid + cross-encoder rerank | 0.91 | 0.83 | 180ms |

## Trade-offs

- Each step adds latency but materially improves accuracy.
- Cross-encoder is the most expensive (forward-pass per candidate) — keep candidates ≤ 30.
- Citation grounding (in `pipeline.py`) lets you reject hallucinations: if no citation, response is suspect.

## Production recommendation

Hybrid + rerank for high-stakes QA (medical, legal, financial).
Just hybrid for chatbot use cases where latency matters more.
Dense-only is acceptable for keyword-loose discovery surfaces.
