import os
import sys

os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

from pyspark.sql import SparkSession
from pyspark.sql.functions import count, lit, coalesce, percentile_approx
from db import get_responses, save_spark_result


def run_spark_pipeline():
    spark = SparkSession.builder \
        .master("local[2]") \
        .appName("HealthData_Percentile_Pipeline") \
        .getOrCreate()

    try:
        raw_responses = get_responses()
        if not raw_responses:
            print("MongoDB(responses 컬렉션)에 처리할 데이터가 없습니다.")
            return

        df = spark.createDataFrame(raw_responses)
        if "source" not in df.columns:
            df = df.withColumn("source", lit("web"))
        else:
            df = df.withColumn("source", coalesce(df["source"], lit("web")))

        df_clean = df.dropna(subset=["age_group", "score"])
        percentiles_list = [round(i / 100.0, 2) for i in range(1, 100)]

        # 1. 출처별 + 연령대별 백분위 (예: kaggle + 20대, naver_form + 20대, web + 20대)
        df_src_age = df_clean.groupBy("source", "age_group").agg(
            count("score").alias("count"),
            percentile_approx("score", percentiles_list, 10000).alias("percentiles")
        )

        # 2. 출처별 전체 백분위 (예: kaggle + ALL, naver_form + ALL, web + ALL)
        df_src_all = df_clean.groupBy("source").agg(
            count("score").alias("count"),
            percentile_approx("score", percentiles_list, 10000).alias("percentiles")
        ).withColumn("age_group", lit("ALL")).select(
            "source", "age_group", "count", "percentiles"
        )

        # 3. 전체 통합 백분위 (ALL + ALL 및 ALL + 연령대)
        df_total_age = df_clean.groupBy("age_group").agg(
            count("score").alias("count"),
            percentile_approx("score", percentiles_list, 10000).alias("percentiles")
        ).withColumn("source", lit("ALL")).select(
            "source", "age_group", "count", "percentiles"
        )

        df_total_all = df_clean.agg(
            count("score").alias("count"),
            percentile_approx("score", percentiles_list, 10000).alias("percentiles")
        ).withColumn("source", lit("ALL")).withColumn("age_group", lit("ALL")).select(
            "source", "age_group", "count", "percentiles"
        )

        df_final = df_src_age.unionByName(df_src_all) \
            .unionByName(df_total_age) \
            .unionByName(df_total_all)

        records = [row.asDict() for row in df_final.collect()]
        save_spark_result(records)
        print(f"MongoDB Atlas (spark_results) 출처별·연령대별 저장 완료! (총 {len(records)}개 그룹)")
    finally:
        spark.stop()


if __name__ == "__main__":
    run_spark_pipeline()