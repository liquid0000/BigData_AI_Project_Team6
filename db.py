import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["sns_health"]          # 데이터베이스 이름
users = db["users"]                # 개인정보 (60일 후 자동 삭제)
responses = db["responses"]        # 익명 응답·점수 (계속 보관)

RETENTION_SECONDS = 60 * 24 * 60 * 60   # 60일을 초로 환산


def init_db():
    """서버 시작 시 한 번 실행: 인덱스 생성"""
    users.create_index("phone", unique=True)          # 같은 연락처 중복 저장 방지
    users.create_index("created_at",
                       expireAfterSeconds=RETENTION_SECONDS)  # 60일 지나면 자동 삭제


def find_user(phone):
    """연락처로 기존 사용자 찾기 (이어하기용). 없으면 None"""
    return users.find_one({"phone": phone}, {"_id": 0, "created_at": 0})


def create_user(phone, name, email, age_group, gender, guardian_info=None):
    """신규 사용자 저장"""
    users.insert_one({
        "phone": phone,
        "name": name,
        "email": email,
        "age_group": age_group,
        "gender": gender,
        "guardian_info": guardian_info,     # 만 14세 미만일 때만 값이 있음
        "privacy_agreed": True,             # 동의 체크 후에만 제출 가능한 화면 구조
        "created_at": datetime.now(timezone.utc),
    })


def save_response(age_group, gender, answers, part_scores, score, status):
    """설문 결과 저장 (이름·연락처 없이 익명으로)"""
    responses.insert_one({
        "age_group": age_group,
        "gender": gender,
        "answers": answers,                 # 25문항 원래 답
        "part_scores": part_scores,         # 영역별 점수
        "score": score,                     # 총점
        "status": status,                   # 5단계 판정
        "created_at": datetime.now(timezone.utc),
    })

def get_responses(fields=None):
    #분석용(PySpark 등): responses 문서를 리스트로 반환
    #fields 예: ["age_group", "score"] → 필요한 필드만 가져옴
    #responses 필드: age_group, gender, answers(25문항 답), part_scores(영역별 0~20),
    #                score(총점 0~100), status(5단계 판정), created_at
    projection = {"_id": 0}
    if fields:
        projection.update({f: 1 for f in fields})
    return list(responses.find({}, projection))


def save_spark_result(records):
    """PySpark 집계 결과를 spark_results 컬렉션에 저장 (이전 결과는 지우고 새로 저장)"""
    spark_results = db["spark_results"]
    spark_results.delete_many({})
    if records:
        spark_results.insert_many(records)