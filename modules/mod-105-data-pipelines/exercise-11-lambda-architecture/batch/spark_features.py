"""Daily batch feature computation: 30-day user aggregates."""
from pyspark.sql import SparkSession, functions as F


def main():
    spark = SparkSession.builder.appName("user-features-batch").getOrCreate()
    events = spark.read.parquet("s3a://datalake/raw/events/")
    end = F.current_date()
    start = F.date_sub(end, 30)

    daily = (events
             .filter(events.event_ts.between(start, end))
             .groupBy("user_id")
             .agg(
                 F.count(F.when(F.col("event_type") == "click", 1)).alias("clicks_30d"),
                 F.count(F.when(F.col("event_type") == "purchase", 1)).alias("purchases_30d"),
                 F.sum("price").alias("revenue_30d"),
                 F.countDistinct("session_id").alias("sessions_30d"),
             ))

    (daily.write.mode("overwrite")
     .parquet("s3a://datalake/features/user_features_batch_v1/"))


if __name__ == "__main__":
    main()
