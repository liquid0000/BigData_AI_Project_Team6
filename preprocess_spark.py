import os
import sys

#PySpark가 워커(Worker) 프로세스를 띄울 때 현재 사용 중인 Python 실행 파일 경로를 명시
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, percentile_approx

# db.py에서 MongoDB 데이터 읽기/쓰기 함수 불러오기
from db import get_responses, save_spark_result

#SparkSession 생성
spark = SparkSession.builder \
    .appName("HealthData_Percentile_Pipeline") \
    .getOrCreate()

#MongoDB에서 설문 응답 데이터 읽기
raw_responses = get_responses()

if not raw_responses:
    print("MongoDB(responses 컬렉션)에 처리할 데이터가 없습니다.")
    spark.stop()
else:
    #Python dict 리스트 -> PySpark DataFrame 변환
    df = spark.createDataFrame(raw_responses)

    #결측치 제거 (연령대 및 점수 미기재 데이터 제외)
    df_clean = df.dropna(subset=["age_group", "score"])

    #연령대별 백분위 연산 (percentile_approx)
    df_percentile = df_clean.groupBy("age_group").agg(
        percentile_approx("score", 0.25, 10000).alias("25th_percentile"),
        percentile_approx("score", 0.50, 10000).alias("median"),
        percentile_approx("score", 0.75, 10000).alias("75th_percentile")
    )

    #연산 결과 콘솔 출력 확인
    #print("=== 연령대별 백분위 연산 결과 ===")
    #df_percentile.show(truncate=False)

    #MongoDB 저장 (db.py의 save_spark_result 함수 연동)
    records = [row.asDict() for row in df_percentile.collect()]
    save_spark_result(records)
    print(f"MongoDB Atlas (spark_results) 저장 완료! (총 {len(records)}개 연령대 그룹)")

    spark.stop()
