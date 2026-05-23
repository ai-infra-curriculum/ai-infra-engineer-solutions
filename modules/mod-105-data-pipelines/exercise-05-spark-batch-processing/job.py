"""NYC-taxi-style batch job: read partitioned Parquet, broadcast + shuffle join, write partitioned + bucketed.

Tunings driven by BENCHMARK.md observations.
"""
from __future__ import annotations

import os

from pyspark.sql import SparkSession, functions as F


INPUT_TRIPS = os.environ.get("INPUT_TRIPS", "s3a://datalake/raw/taxi-trips/")
INPUT_ZONES = os.environ.get("INPUT_ZONES", "s3a://datalake/dim/taxi-zones/")
INPUT_USERS = os.environ.get("INPUT_USERS", "s3a://datalake/dim/users/")
OUTPUT = os.environ.get("OUTPUT", "s3a://datalake/curated/taxi-trips-enriched/")
SHUFFLE_PARTS = int(os.environ.get("SPARK_SHUFFLE_PARTS", 200))


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("taxi-enrich")
        .config("spark.sql.shuffle.partitions", SHUFFLE_PARTS)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.parquet.compression.codec", "zstd")
        .getOrCreate()
    )


def main():
    spark = build_spark()

    trips = (
        spark.read.parquet(INPUT_TRIPS)
        .filter(F.col("pickup_ts") >= F.lit("2026-01-01"))
    )
    zones = spark.read.parquet(INPUT_ZONES)        # ~300 rows
    users = spark.read.parquet(INPUT_USERS)        # ~50M rows

    # Broadcast join on small dimension
    trips_zoned = trips.join(F.broadcast(zones), on="pu_location_id", how="left")

    # Repartition for explicit shuffle join with big dimension
    trips_repart = trips_zoned.repartition(SHUFFLE_PARTS, "user_id")
    users_repart = users.repartition(SHUFFLE_PARTS, "user_id")
    enriched = trips_repart.join(users_repart, on="user_id", how="left")

    # SQL-style aggregation
    enriched.createOrReplaceTempView("trips")
    daily = spark.sql("""
        SELECT
          DATE_TRUNC('day', pickup_ts) AS day,
          user_segment,
          zone_name,
          COUNT(*)            AS trips,
          AVG(fare_amount)    AS avg_fare,
          SUM(total_amount)   AS revenue
        FROM trips
        GROUP BY 1, 2, 3
    """)

    (
        enriched
        .withColumn("day", F.to_date("pickup_ts"))
        .write
        .mode("overwrite")
        .partitionBy("day")
        .bucketBy(64, "user_id")          # bucketing for join reuse downstream
        .sortBy("user_id")
        .saveAsTable("curated.trips_enriched")
    )

    daily.write.mode("overwrite").partitionBy("day").parquet(OUTPUT + "/agg/")
    spark.stop()


if __name__ == "__main__":
    main()
