import os
import re
import pandas as pd
import db
from preprocess_spark import run_spark_pipeline

# ==============================================================================
# 1. data/ 폴더 내 파일 경로 및 컬럼명 설정 (실제 파일명·컬럼명에 맞게 수정하세요)
# ==============================================================================
KAGGLE_FILE = "data/kaggle_sns.csv"          # 캐글 CSV 파일 경로 (없으면 None)
NAVER_FILE = "data/naver_form_sns.xlsx"    # 네이버폼 CSV 또는 XLSX 파일 경로 (없으면 None)

# 캐글 파일 설정
KAGGLE_CONFIG = {
    "age_col": "Age",                        # 나이 또는 연령대 컬럼명
    "score_col": "Addicted_Score",           # 점수 컬럼명
    "max_raw_score": 10.0,                   # 원본 점수 만점 기준 (예: 10점 만점이면 10.0)
    "min_raw_score": 1.0,                    # 원본 점수 최솟값 (0점부터 시작이면 0.0)
    "higher_is_worse": True                  # True: 높을수록 중독/위험(점수 반전) / False: 높을수록 건강
}

# 네이버폼 파일 설정 (25문항 개별 응답 컬럼이 있는 경우)
NAVER_CONFIG = {
    "age_col": "연령대를 선택해 주세요",      # 네이버폼 연령대 질문 컬럼명
    "gender_col": "성별을 선택해 주세요",     # 네이버폼 성별 질문 컬럼명 (없으면 None)
    "question_cols": [f"Q{i}" for i in range(1, 26)],
    "positive_questions": {3, 5, 8, 10, 13, 15, 18, 20, 21, 22, 24, 25}
}


# ==============================================================================
# 2. 공통 변환 함수 (연령대 통일 & 점수 환산)
# ==============================================================================
def normalize_age_group(raw_age):
    """숫자 나이 또는 다양한 연령대 텍스트를 웹 서비스 6개 구간으로 통일"""
    if pd.isna(raw_age):
        return None
    s = str(raw_age).strip()

    valid_groups = {
        "만 14세 미만",
        "만 14세 이상 ~ 만 19세 미만",
        "20대",
        "30대",
        "40대",
        "50대 이상"
    }
    if s in valid_groups:
        return s

    nums = re.findall(r"\d+", s)
    if not nums:
        return None
    age = int(nums[0])

    if "10대" in s:
        return "만 14세 이상 ~ 만 19세 미만"
    if age < 14:
        return "만 14세 미만"
    elif age < 20:
        return "만 14세 이상 ~ 만 19세 미만"
    elif age < 30:
        return "20대"
    elif age < 40:
        return "30대"
    elif age < 50:
        return "40대"
    else:
        return "50대 이상"


def extract_likert_value(val):
    """'1', '1점', '1. 전혀 아니다' 등에서 1~5 정수 추출"""
    if pd.isna(val):
        return None
    m = re.search(r"[1-5]", str(val))
    return int(m.group()) if m else None


def read_table(filepath):
    if filepath.endswith(".csv"):
        try:
            return pd.read_csv(filepath, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(filepath, encoding="cp949")
    return pd.read_excel(filepath)


# ==============================================================================
# 3. 캐글 데이터 변환기
# ==============================================================================
def load_kaggle_docs(filepath, cfg):
    if not filepath or not os.path.exists(filepath):
        print(f"[건너뜀] 캐글 파일을 찾을 수 없습니다: {filepath}")
        return []

    df = read_table(filepath)
    docs = []
    span = cfg["max_raw_score"] - cfg["min_raw_score"]

    for _, row in df.iterrows():
        age_group = normalize_age_group(row.get(cfg["age_col"]))
        raw_score = row.get(cfg["score_col"])
        if not age_group or pd.isna(raw_score):
            continue

        try:
            val = float(raw_score)
        except (ValueError, TypeError):
            continue

        ratio = max(0.0, min(1.0, (val - cfg["min_raw_score"]) / span))
        health_score = round((1.0 - ratio) * 100) if cfg["higher_is_worse"] else round(ratio * 100)

        docs.append({
            "source": "kaggle",
            "age_group": age_group,
            "score": int(health_score)
        })

    print(f"[캐글] 변환 완료: {len(docs)}건")
    return docs


# ==============================================================================
# 4. 네이버폼 데이터 변환기 (웹 설문과 동일한 25문항 역채점 적용)
# ==============================================================================
def load_naver_docs(filepath, cfg):
    if not filepath or not os.path.exists(filepath):
        print(f"[건너뜀] 네이버폼 파일을 찾을 수 없습니다: {filepath}")
        return []

    df = read_table(filepath)
    docs = []

    q_cols = cfg["question_cols"]
    if not all(col in df.columns for col in q_cols):
        auto_cols = [c for c in df.columns if re.match(r"^(Q|q)?\d+[\.\)\s]", str(c).strip())]
        if len(auto_cols) == 25:
            q_cols = auto_cols
        else:
            print("[오류] 네이버폼 25개 문항 컬럼을 매칭하지 못했습니다. NAVER_CONFIG['question_cols']를 확인해 주세요.")
            return []

    for _, row in df.iterrows():
        age_group = normalize_age_group(row.get(cfg["age_col"]))
        if not age_group:
            continue

        total_health_score = 0
        valid_row = True

        for idx, col in enumerate(q_cols, start=1):
            raw_val = extract_likert_value(row.get(col))
            if raw_val is None:
                valid_row = False
                break
            health_val = (raw_val - 1) if idx in cfg["positive_questions"] else (5 - raw_val)
            total_health_score += health_val

        if not valid_row:
            continue

        docs.append({
            "source": "naver_form",
            "age_group": age_group,
            "gender": str(row.get(cfg["gender_col"])).strip() if cfg.get("gender_col") in df.columns else None,
            "score": int(total_health_score)
        })

    print(f"[네이버폼] 변환 완료: {len(docs)}건")
    return docs


# ==============================================================================
# 5. MongoDB Atlas 통합 적재 및 Spark 통계 즉시 갱신
# ==============================================================================
def main():
    responses_col = db.db["responses"]

    kaggle_docs = load_kaggle_docs(KAGGLE_FILE, KAGGLE_CONFIG)
    naver_docs = load_naver_docs(NAVER_FILE, NAVER_CONFIG)

    if kaggle_docs:
        responses_col.delete_many({"source": "kaggle"})
        responses_col.insert_many(kaggle_docs)
        print(f"MongoDB 'responses'에 캐글 {len(kaggle_docs)}건 적재 완료!")

    if naver_docs:
        responses_col.delete_many({"source": "naver_form"})
        responses_col.insert_many(naver_docs)
        print(f"MongoDB 'responses'에 네이버폼 {len(naver_docs)}건 적재 완료!")

    # 적재 직후 preprocess_spark.py의 백분위 파이프라인을 자동 실행해 spark_results 갱신
    if kaggle_docs or naver_docs:
        run_spark_pipeline()
    else:
        print("적재할 외부 데이터가 없습니다. 파일 경로와 컬럼명을 확인해 주세요.")


if __name__ == "__main__":
    main()