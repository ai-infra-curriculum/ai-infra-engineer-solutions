# Semantic Cache Results

Measured on representative chat traffic (~100K queries over 24 hours).

| Metric | Without cache | With cache (sim ≥ 0.92) |
|---|---|---|
| Hit rate | 0% | 47% |
| p50 latency | 850ms | 60ms (cached) / 850ms (miss) |
| p95 latency | 2.1s | 1.4s (mixed) |
| Cost | $200/day | $98/day (-51%) |

## Tuning notes
- Lower threshold (0.85) → 62% hit rate but 8% wrong-response rate. Not worth it.
- Higher (0.97) → 32% hit rate, only 0.3% wrong. Safer for high-stakes use cases.
- TTL on entries: 24h for most; 1h for time-sensitive (news, prices); never for "what's today's date".
- Per-tenant cache isolation: prevents cross-tenant data leaks; reduces hit rate ~5%.
