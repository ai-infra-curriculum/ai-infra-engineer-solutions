# Lambda Reconciliation

## Why it matters
The whole point of Lambda is to combine streaming (fast, imprecise) with batch
(slow, accurate). When the two diverge in ways that affect serving, you must
notice — quickly — and decide whether to:

1. Adjust streaming window/aggregation (the usual root cause)
2. Adjust batch to match streaming (rare; usually means batch is wrong)
3. Treat as an incident if batch is the source-of-truth and streaming exposes a real bug

## What the diff script does
Samples 1000 users daily. For each, compares streaming `clicks_5m` against the
batch-derived daily average (`clicks_30d / 30`). Flags when streaming exceeds
twice the daily-average baseline + 5 — a heuristic for "streaming is producing
spurious spikes."

## When the drift rate exceeds 5%
- Check Kafka consumer lag (probable: backlogged events arriving compressed)
- Check Flink restart/checkpoint logs (probable: state restore replayed events)
- Check upstream producer rate (possible: real burst that streaming caught but batch will see)

## Kappa migration path
When streaming is mature enough (low drift, accurate windows, replayable),
collapse Lambda → Kappa. Indicators:
- Drift rate < 1% sustained for 30 days
- Kafka retention extended to cover replay window (~30 days)
- All batch consumers updated to read streaming output
