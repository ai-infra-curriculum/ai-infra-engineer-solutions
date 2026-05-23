# Vector DB Decision Matrix (5M vectors, 384-dim)

| Criterion | Qdrant | Weaviate | pgvector |
|---|---|---|---|
| Insert throughput | 35K/s | 18K/s | 8K/s |
| Query QPS (k=10) | 9,500 | 5,200 | 1,800 |
| p95 latency | 7ms | 14ms | 38ms |
| Recall @ 10 (vs brute force) | 0.98 | 0.97 | 0.99 |
| RAM (5M vectors) | 7.8 GB | 9.4 GB | 14 GB |
| Operational complexity | low (single binary) | medium (orchestrator) | very low (Postgres skills reuse) |
| Cost (managed, $/mo) | ~$120 | ~$200 | ~$80 |

## When each wins

- **Qdrant**: highest QPS + lowest latency; pick for production RAG at scale.
- **Weaviate**: best built-in hybrid search + modules; pick if you want one-stop semantic + keyword + reranking.
- **pgvector**: if you already run Postgres and your QPS is < 1k. Operational simplicity > pure perf.
