import os
import re
import pandas as pd
import db
from preprocess_spark import run_spark_pipeline

# data/ 폴더 경로에 맞게 수정하세요
NAVER_FILE = "data/naver_form_data.csv"
KAGGLE_FILE = "data/Social_media_impact_on_life.csv"


def read_any_table(filepath):
    """확장자와 무관하게 실제 파일 시그니처(xlsx/csv)를 감지하여 로드"""
    with open(filepath, "rb") as f:
        sig = f.read(4)
    if sig == b"PK\x03\x04":
        return pd.read_excel(filepath)
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(filepath, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(filepath, encoding="latin1")


def normalize_age_group(raw_age):
    """네이버폼/캐글 연령을 웹 서비스 6개 연령대 문자열로 통일"""
    if pd.isna(raw_age):
        return None
    s = str(raw_age).strip()

    if "10대" in s:
        return "만 14세 이상 ~ 만 19세 미만"
    if s in {"20대", "30대", "40대", "50대 이상", "만 14세 미만", "만 14세 이상 ~ 만 19세 미만"}:
        return s

    nums = re.findall(r"\d+", s)
    if not nums:
        return None
    age = int(nums[0])

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


# ==============================================================================
# 1. 네이버폼 데이터(79건) -> 웹 결과창 5개 영역(각 20점, 총 100점) 환산
# ==============================================================================
def load_naver_docs(filepath):
    if not filepath or not os.path.exists(filepath):
        print(f"[건너뜀] 네이버폼 파일 없음: {filepath}")
        return []

    df = read_any_table(filepath)
    docs = []

    col_age = "귀하의 연령대는 어떻게 되시나요?(*)"
    col_time = "하루 평균 소셜미디어 이용 시간은 어느 정도인가요?(*)"
    col_comp = "타인의 SNS 게시물을 보고 나 자신과 비교하며 상대적 박탈감이나 우울함을 느낀 적이 있다.(*)"
    col_heal = "SNS를 통해 필요한 정보를 얻거나 정서적 위안 및 힐링을 얻는다.(*)"
    col_fomo = "특별한 목적 없이 습관적으로 SNS를 확인하지 않으면 불안감(FOMO)을 느낀다.(*)"
    col_rel = "SNS에서의 소통이 현실 세계의 인간관계 형성 및 유지에 긍정적인 도움을 준다.(*)"

    time_score_map = {
        "1시간 미만": 20,
        "1시간 이상 ~ 2시간 미만": 15,
        "2시간 이상 ~ 4시간 미만": 10,
        "4시간 이상": 5,
    }

    for _, row in df.iterrows():
        age_group = normalize_age_group(row.get(col_age))
        if not age_group:
            continue

        try:
            # PART1: 이용 습관 및 자율성 (이용시간 기반, 20점)
            t_str = str(row.get(col_time, "")).strip()
            p1 = time_score_map.get(t_str, 10)

            # PART2: 건강한 자아 및 자존감 (상대적 박탈감 역채점: 1->20, 5->0)
            v_comp = int(float(row[col_comp]))
            p2 = (5 - v_comp) * 5

            # PART3: 정서 및 감정 안정성 (정서적 위안/힐링 정채점: 1->0, 5->20)
            v_heal = int(float(row[col_heal]))
            p3 = (v_heal - 1) * 5

            # PART4: 자기 통제력 및 여유 (FOMO 불안감 역채점: 1->20, 5->0)
            v_fomo = int(float(row[col_fomo]))
            p4 = (5 - v_fomo) * 5

            # PART5: 신체 건강 및 대인관계 (현실 인간관계 도움 정채점: 1->0, 5->20)
            v_rel = int(float(row[col_rel]))
            p5 = (v_rel - 1) * 5
        except (ValueError, TypeError, KeyError):
            continue

        part_scores = {"PART1": p1, "PART2": p2, "PART3": p3, "PART4": p4, "PART5": p5}
        total_score = p1 + p2 + p3 + p4 + p5

        docs.append({
            "source": "naver_form",
            "age_group": age_group,
            "part_scores": part_scores,
            "score": int(total_score)
        })

    print(f"[네이버폼] 변환 완료: {len(docs)}건")
    return docs


# ==============================================================================
# 2. 캐글 데이터(4,500건) -> 웹 결과창 5개 영역(각 20점, 총 100점) 환산
# ==============================================================================
def load_kaggle_docs(filepath):
    if not filepath or not os.path.exists(filepath):
        print(f"[건너뜀] 캐글 파일 없음: {filepath}")
        return []

    df = read_any_table(filepath)
    docs = []

    comp_map = {
        "Never": 20,
        "Rarely": 15,
        "Sometimes": 10,
        "Frequently": 5,
        "Always": 0
    }

    for _, row in df.iterrows():
        age_group = normalize_age_group(row.get("Age"))
        if not age_group:
            continue

        try:
            # PART1: 이용 습관 및 자율성 (일일 이용시간 1~12시간 기준 역환산, 20점)
            daily_hrs = float(row["Daily_Usage_Hours"])
            p1 = round(max(0.0, min(20.0, (12.0 - daily_hrs) / 11.0 * 20.0)))

            # PART2: 건강한 자아 및 자존감 (타인 비교 빈도, 20점)
            comp_str = str(row.get("Social_Comparison_Frequency", "")).strip()
            p2 = comp_map.get(comp_str, 10)

            # PART3: 정서 및 감정 안정성 (스트레스 역환산 + 정신건강지수, 20점)
            stress = float(row["Perceived_Stress_Score"]) if pd.notna(row.get("Perceived_Stress_Score")) else 15.0
            mhi = float(row["Mental_Health_Index"]) if pd.notna(row.get("Mental_Health_Index")) else 75.0
            stress_health = max(0.0, min(1.0, (40.0 - stress) / 40.0))
            mhi_health = max(0.0, min(1.0, mhi / 100.0))
            p3 = round(((stress_health + mhi_health) / 2.0) * 20.0)

            # PART4: 자기 통제력 및 여유 (심야 이용 여부 + 주말 초과 이용시간, 20점)
            late_night = bool(row["Late_Night_Usage"])
            wk_extra = float(row["Weekend_Extra_Hours"])
            late_score = 0.0 if late_night else 10.0
            wk_score = max(0.0, min(10.0, (4.0 - wk_extra) / 4.0 * 10.0))
            p4 = round(late_score + wk_score)

            # PART5: 신체 건강 및 대인관계 (수면시간 + 수면질 + 학업GPA, 20점)
            sleep_hrs = float(row["Sleep_Duration_Hours"])
            sleep_qual = float(row["Sleep_Quality_Score"])  # 1 ~ 5
            gpa = float(row["Academic_Performance_GPA"]) if pd.notna(row.get("Academic_Performance_GPA")) else 3.2
            s_hrs_norm = max(0.0, min(1.0, (sleep_hrs - 4.0) / 4.5))
            s_qual_norm = max(0.0, min(1.0, (sleep_qual - 1.0) / 4.0))
            gpa_norm = max(0.0, min(1.0, (gpa - 2.0) / 2.0))
            p5 = round(((s_hrs_norm + s_qual_norm + gpa_norm) / 3.0) * 20.0)
        except (ValueError, TypeError, KeyError):
            continue

        part_scores = {"PART1": p1, "PART2": p2, "PART3": p3, "PART4": p4, "PART5": p5}
        total_score = p1 + p2 + p3 + p4 + p5

        docs.append({
            "source": "kaggle",
            "age_group": age_group,
            "gender": str(row.get("Gender", "")).strip() or None,
            "part_scores": part_scores,
            "score": int(total_score)
        })

    print(f"[캐글] 변환 완료: {len(docs)}건")
    return docs


def main():
    responses_col = db.db["responses"]

    naver_docs = load_naver_docs(NAVER_FILE)
    kaggle_docs = load_kaggle_docs(KAGGLE_FILE)

    if naver_docs:
        responses_col.delete_many({"source": "naver_form"})
        responses_col.insert_many(naver_docs)
        print(f"MongoDB 'responses'에 네이버폼 {len(naver_docs)}건 적재 완료!")

    if kaggle_docs:
        responses_col.delete_many({"source": "kaggle"})
        responses_col.insert_many(kaggle_docs)
        print(f"MongoDB 'responses'에 캐글 {len(kaggle_docs)}건 적재 완료!")

    if naver_docs or kaggle_docs:
        run_spark_pipeline()


if __name__ == "__main__":
    main()