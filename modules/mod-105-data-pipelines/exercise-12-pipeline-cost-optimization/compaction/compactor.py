"""Compact small Parquet files into 128MB targets. Cuts S3 list + scan cost."""
from __future__ import annotations

import argparse

from pyspark.sql import SparkSession


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in",  dest="in_path",  required=True)
    p.add_argument("--out", dest="out_path", required=True)
    p.add_argument("--target-size-mb", type=int, default=128)
    args = p.parse_args()

    spark = SparkSession.builder.appName("compactor").getOrCreate()
    df = spark.read.parquet(args.in_path)

    rows = df.count()
    bytes_per_row_est = 200    # tune per dataset
    target_files = max(1, (rows * bytes_per_row_est) // (args.target_size_mb * 1024 * 1024))
    df.coalesce(target_files).write.mode("overwrite").parquet(args.out_path)
    print(f"compacted to {target_files} files")


if __name__ == "__main__":
    main()
