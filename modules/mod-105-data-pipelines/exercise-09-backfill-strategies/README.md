# Backfill Strategies — Solution

Reference for [learning exercise-09](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-09-backfill-strategies/README.md).

```bash
# Dry-run shows execution plan; nothing written.
python backfill.py --strategy parallel-date --start 2026-01-01 --end 2026-01-31 --dry-run

# Real run with concurrency cap and dependency-aware ordering.
python backfill.py --strategy parallel-shard --start 2026-01-01 --end 2026-01-31 \
  --shards 4 --concurrency 8

# Resume failed sub-ranges only.
python backfill.py --strategy parallel-date --start 2026-01-01 --end 2026-01-31 --retry-failed
```

## Benchmark (90 day × 4 shard backfill, simulated 50ms/unit)

| Strategy | Wall-clock | Notes |
|---|---|---|
| sequential | 18.0s | safest; trivially ordered |
| parallel-date (concurrency=8) | 2.4s | 7.5× faster; safe if shards within a day are independent |
| parallel-shard (concurrency=8) | 2.7s | day-by-day ordering preserved; safest for inter-day dependencies |

Every run logged to `backfill_audit.db` for incident review.
