# Spark Batch Processing — Solution

Reference for [learning exercise-05](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-05-spark-batch-processing/README.md).

- `job.py` — PySpark job with broadcast + shuffle joins, partitioned + bucketed write.
- `BENCHMARK.md` — measured impact of each tuning.

```bash
spark-submit --master local[*] --conf spark.sql.shuffle.partitions=64 job.py
```
