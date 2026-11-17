import os
import sys

# PySpark가 워커(Worker) 프로세스를 띄울 때 현재 사용 중인 Python 실행 파일 경로 명시
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

from pyspark.sql import SparkSession
from pyspark.sql.functions import count, lit, percentile_approx
from db import get_responses, save_spark_result

def run_spark_pipeline():
    spark = SparkSession.builder \
        .master("local[2]") \
        .appName("HealthData_Percentile_Pipeline") \
        .getOrCreate()

    try:
        # MongoDB에서 설문 응답 데이터 읽기
        raw_responses = get_responses()
        if not raw_responses:
            print("MongoDB(responses 컬렉션)에 처리할 데이터가 없습니다.")
            return

        # Python dict 리스트 -> PySpark DataFrame 변환
        df = spark.createDataFrame(raw_responses)

        # 결측치 제거 (연령대 및 점수 미기재 데이터 제외)
        df_clean = df.dropna(subset=["age_group", "score"])

        # 1 ~ 99 백분위 리스트 생성 ([0.01, 0.02, ..., 0.99])
        percentiles_list = [round(i / 100.0, 2) for i in range(1, 100)]

        # 1. 연령대별 1~99 백분위 배열 및 표본 수 연산
        df_age = df_clean.groupBy("age_group").agg(
            count("score").alias("count"),
            percentile_approx("score", percentiles_list, 10000).alias("percentiles")
        )

        # 2. 전체 데이터셋 기준 1~99 백분위 배열 및 표본 수 연산 (age_group = "ALL")
        df_all = df_clean.agg(
            count("score").alias("count"),
            percentile_approx("score", percentiles_list, 10000).alias("percentiles")
        ).withColumn("age_group", lit("ALL")).select(
            "age_group", "count", "percentiles"
        )

        # 연령대별 결과와 전체 결과 합치기
        df_final = df_age.unionByName(df_all)

        # MongoDB Atlas (spark_results) 저장
        records = [row.asDict() for row in df_final.collect()]
        save_spark_result(records)
        print(f"MongoDB Atlas (spark_results) 저장 완료! (총 {len(records)}개 그룹)")
    finally:
        spark.stop()

if __name__ == "__main__":
    run_spark_pipeline()
