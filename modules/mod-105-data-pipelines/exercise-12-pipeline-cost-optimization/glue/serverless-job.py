"""AWS Glue serverless job. Pays per DPU-second of runtime — no always-on EMR cost."""
import sys

from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext


def main():
    args = getResolvedOptions(sys.argv, ["JOB_NAME", "input", "output"])
    sc = SparkContext()
    glue = GlueContext(sc)
    spark = glue.spark_session

    df = spark.read.parquet(args["input"])
    df.write.mode("overwrite").partitionBy("day").parquet(args["output"])


if __name__ == "__main__":
    main()
