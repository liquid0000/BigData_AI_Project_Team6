from pyspark.sql import SparkSession
from pyspark.sql.functions import avg

spark = SparkSession.builder \
    .master("local[2]") \
    .appName("SNS_Analysis") \
    .getOrCreate()

try:
    df = spark.read.csv(
        "data/responses.csv",
        header=True,
        inferSchema=True
    )

    print("=== SNS 데이터 ===")
    df.show()

    print("=== 평균 분석 ===")
    df.select(
        avg("score").alias("avg_score")
    ).show()

finally:
    spark.stop()
