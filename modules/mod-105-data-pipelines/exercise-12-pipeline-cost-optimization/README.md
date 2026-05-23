# Pipeline Cost Optimization — Solution

Reference for [learning exercise-12](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-12-pipeline-cost-optimization/README.md).

6 techniques applied to mod-105's daily-job pipeline. Combined target: **62% cost reduction with no loss of functionality.**

| Technique | Before | After | Saving |
|---|---|---|---|
| Spot instances for batch | $0.40/h × 8h × 30d = $96 | $0.12/h × 8h × 30d = $29 | **70%** |
| Parquet+zstd over CSV+gzip | $48/mo storage, scans 5GB/job | $18/mo storage, scans 1.2GB/job | **63%** |
| Date partitioning + pruning | 5 TB scanned/mo | 0.9 TB scanned/mo | **82%** |
| File size tuning (32MB → 128MB) | 30K files; 6 min S3 list | 7K files; 1 min S3 list | **5×** |
| Query result cache (BigQuery) | $300/mo @ 10TB scanned | $120/mo @ 4TB scanned | **60%** |
| Serverless (Glue) for ad-hoc | $96/mo always-on EMR | $14/mo Glue jobs | **85%** |
| **Combined** | $1100/mo | **~$420/mo** | **62%** |

## Files

```
exercise-12-pipeline-cost-optimization/
├── README.md, COST_BREAKDOWN.md
├── spot/spark-defaults.conf
├── partition-pruning/airflow_dag.py
├── compaction/compactor.py
└── glue/serverless-job.py
```
