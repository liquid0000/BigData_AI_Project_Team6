from pyspark.sql import SparkSession
from pyspark.sql.functions import col, percentile_approx

#순수 로컬 테스트용 SparkSession 생성
spark = SparkSession.builder \
    .appName("HealthData_Percentile_Pipeline") \
    .getOrCreate()

#데이터 불러오기 경로도 체크
df_naver = spark.read.csv(
    "data/naver_form_data.csv",
    header=True,
    inferSchema=True
)

df_kaggle = spark.read.csv(
    "data/Social_media_impact_on_life.csv",
    header=True,
    inferSchema=True
)

#컬럼명 변경
df_naver = (
    df_naver
    .withColumnRenamed("귀하의 연령대는 어떻게 되시나요?(*)", "age_group")
    .withColumnRenamed("타인의 SNS 게시물을 보고 나 자신과 비교하며 상대적 박탈감이나 우울함을 느낀 적이 있다.(*)", "q1_depress")
    .withColumnRenamed("SNS를 통해 필요한 정보를 얻거나 정서적 위안 및 힐링을 얻는다.(*)", "q2_healing")
    .withColumnRenamed("특별한 목적 없이 습관적으로 SNS를 확인하지 않으면 불안감(FOMO)을 느낀다.(*)", "q3_fomo")
    .withColumnRenamed("SNS에서의 소통이 현실 세계의 인간관계 형성 및 유지에 긍정적인 도움을 준다.(*)", "q4_social")
)

#부정 문항 역채점
df_norm = df_naver.withColumn(
    "q1_score",
    100 - ((col("q1_depress") - 1) * 25)
)

df_norm = df_norm.withColumn(
    "q3_score",
    100 - ((col("q3_fomo") - 1) * 25)
)

#긍정 문항 정방향 채점
df_norm = df_norm.withColumn(
    "q2_score",
    (col("q2_healing") - 1) * 25
)

df_norm = df_norm.withColumn(
    "q4_score",
    (col("q4_social") - 1) * 25
)

#종합 점수 계산
df_norm = df_norm.withColumn(
    "total_score",
    (
        col("q1_score")
        + col("q2_score")
        + col("q3_score")
        + col("q4_score")
    ) / 4
)
# 연령대가 40대가 없어서 지우는 용도 깃허브다운받은 csv기준
df_norm = df_norm.dropna(subset=["age_group"])

#연령대별 백분위 계산
df_percentile = df_norm.groupBy("age_group").agg(
    percentile_approx("total_score", 0.25, 10000).alias("25th_percentile"),
    percentile_approx("total_score", 0.50, 10000).alias("median"),
    percentile_approx("total_score", 0.75, 10000).alias("75th_percentile")
)

#결과 콘솔 출력 확인용도
#print("=== 연령대별 백분위 연산 결과 ===")
#df_percentile.show(truncate=False)

# ==========================================
#나중에 .env 파일을 있을때 사용할 MongoDB 저장 로직 지금은 혼자 돌리는 개발용도
# ==========================================
# from db import db
# pdf_result = df_percentile.toPandas()
# records = pdf_result.to_dict(orient="records")
# collection = db["percentile_result"]
# collection.delete_many({})
# if records:
#     collection.insert_many(records)
# print("MongoDB Atlas(percentile_result) 저장 완료!")

spark.stop()