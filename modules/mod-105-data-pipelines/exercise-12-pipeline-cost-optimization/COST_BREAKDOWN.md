# Cost Breakdown

## Methodology
- Baselines measured against AWS Cost Explorer over 30 days of the pre-optimization pipeline.
- Each technique applied incrementally; cost re-measured after 7 days of operation.

## Per-technique details

### Spot for batch
- EMR with 100% spot task nodes (3× over-provisioned to absorb evictions).
- Critical: master + core on on-demand, task nodes on spot.
- Configured graceful decommissioning + job retry settings (`spark-defaults.conf`).
- Realized 70% savings; observed 4% additional retries from spot reclaim.

### Columnar + compression
- Migrated raw landing from CSV/gzip → Parquet/zstd.
- 63% smaller storage; 4× faster scans.

### Partition pruning
- Re-organized warehouse tables to be date-partitioned.
- Updated all daily-aggregate queries to include `WHERE day = ?`.
- BigQuery + Athena now skip non-matching partitions entirely.

### File size tuning
- Compactor job runs nightly, collapsing 30K small files → 7K ~128MB files.
- S3 list operations dropped from 6 min to 1 min on cold runs.

### Query result caching
- BigQuery automatic 24h cache for identical queries (free).
- Forced cache hits by stabilizing query text (no embedded timestamps in queries).
- Saved 60% of warehouse scan cost.

### Serverless for ad-hoc
- Replaced always-on EMR cluster for one-off jobs with AWS Glue jobs (per-DPU-second).
- Always-on cluster cost $96/mo; Glue $14/mo for the same workload.

## What we deliberately did NOT cut
- Daily backup retention to 90 days (compliance)
- ZSTD level (kept at 3, not 22) — higher levels would save more but slow scans
- Real-time path remains on dedicated Flink jobs (no spot for streaming)
