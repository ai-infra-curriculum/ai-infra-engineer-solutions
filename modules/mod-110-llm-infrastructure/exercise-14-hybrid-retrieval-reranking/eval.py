"""Score retrieval quality: recall@k + nDCG."""
from __future__ import annotations

import json
import math

from retrieve import dense_search, hybrid_search
from rerank import rerank


def recall_at_k(retrieved: list, relevant: set[str], k: int = 5) -> float:
    top = {d.id for d in retrieved[:k]}
    if not relevant:
        return 0.0
    return len(top & relevant) / len(relevant)


def ndcg_at_k(retrieved: list, relevant: set[str], k: int = 5) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, d in enumerate(retrieved[:k]) if d.id in relevant)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return dcg / idcg if idcg else 0.0


def main():
    cases = [json.loads(line) for line in open("golden_eval.jsonl")]
    dense_metrics = []
    hybrid_metrics = []
    reranked_metrics = []

    for case in cases:
        q = case["question"]
        relevant = set(case["relevant_ids"])

        d = dense_search(q, k=10)
        dense_metrics.append((recall_at_k(d, relevant), ndcg_at_k(d, relevant)))

        h = hybrid_search(q, "data/corpus.tsv", k=10)
        hybrid_metrics.append((recall_at_k(h, relevant), ndcg_at_k(h, relevant)))

        r = rerank(q, h, top_k=5)
        reranked_metrics.append((recall_at_k(r, relevant), ndcg_at_k(r, relevant)))

    def avg(metrics, idx):
        return sum(m[idx] for m in metrics) / len(metrics)

    print(f"{'method':<20} {'recall@5':>10} {'nDCG@5':>10}")
    for name, m in (("dense", dense_metrics), ("hybrid", hybrid_metrics), ("hybrid+rerank", reranked_metrics)):
        print(f"{name:<20} {avg(m, 0):>10.3f} {avg(m, 1):>10.3f}")


if __name__ == "__main__":
    main()
