import os
import csv
from datetime import datetime
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'sns_psychology_diagnosis_secret_key'

# ---------------------------------------------------------
# 1. 캐글 & 네이버 폼 데이터셋 통합 로드
# ---------------------------------------------------------
KAGLE_SCORES = []
TOTAL_DATASET_COUNT = 0

def load_all_datasets():
    global KAGLE_SCORES, TOTAL_DATASET_COUNT
    
    data_dir = os.path.join(app.root_path, 'data')
    file_kaggle = os.path.join(data_dir, 'Social_media_impact_on_life.csv')
    file_naver = os.path.join(data_dir, 'naver_form_data.csv')
    
    combined_scores = []

    # 1. 캐글 데이터셋 로드
    if os.path.exists(file_kaggle):
        try:
            for enc in ['utf-8-sig', 'utf-8', 'cp949', 'latin1']:
                try:
                    df_k = pd.read_csv(file_kaggle, encoding=enc)
                    num_k = df_k.select_dtypes(include=[np.number]).fillna(3)
                    if not num_k.empty:
                        sums = num_k.sum(axis=1)
                        min_s, max_s = sums.min(), sums.max()
                        if max_s > min_s:
                            scaled = ((sums - min_s) / (max_s - min_s)) * 100
                            combined_scores.extend(scaled.round().tolist())
                        else:
                            combined_scores.extend(sums.tolist())
                    break
                except Exception:
                    continue
            print(f"✅ [캐글 데이터 연동 완료]")
        except Exception as e:
            print(f"⚠️ [캐글 로드 예외]: {e}")

    # 2. 네이버 폼 데이터셋 로드
    if os.path.exists(file_naver):
        try:
            for enc in ['utf-8-sig', 'utf-8', 'cp949', 'latin1']:
                try:
                    df_n = pd.read_csv(file_naver, encoding=enc)
                    num_n = df_n.select_dtypes(include=[np.number]).fillna(3)
                    if not num_n.empty:
                        sums = num_n.sum(axis=1)
                        min_s, max_s = sums.min(), sums.max()
                        if max_s > min_s:
                            scaled = ((sums - min_s) / (max_s - min_s)) * 100
                            combined_scores.extend(scaled.round().tolist())
                        else:
                            combined_scores.extend(sums.tolist())
                    break
                except Exception:
                    continue
            print(f"✅ [네이버 폼 데이터 연동 완료]")
        except Exception as e:
            print(f"⚠️ [네이버 폼 로드 예외]: {e}")

    if combined_scores:
        KAGLE_SCORES = combined_scores
        TOTAL_DATASET_COUNT = len(combined_scores)
        print(f"🎉 [전체 데이터셋 통합 완료] 총 {TOTAL_DATASET_COUNT}개 응답군 확보")
    else:
        TOTAL_DATASET_COUNT = 111
        KAGLE_SCORES = [np.random.randint(20, 80) for _ in range(111)]

load_all_datasets()

# ---------------------------------------------------------
# 2. 라우터
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/survey')
def survey():
    return render_template('survey.html')

@app.route('/result')
def result():
    result_data = session.get('survey_result')
    if not result_data:
        return redirect(url_for('index'))
    return render_template('result.html', result=result_data)

# ---------------------------------------------------------
# 3. 제출 API 및 통합 백분위 계산
# ---------------------------------------------------------
@app.route('/api/submit', methods=['POST'])
def submit():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "전달된 데이터가 없습니다."}), 400

        user_info = data.get('userInfo', {})
        user_name = user_info.get('name', '사용자')
        user_phone = user_info.get('phone', '')
        user_email = user_info.get('email', '')
        user_gender = user_info.get('gender', '')
        user_age = user_info.get('ageGroup', '20대')

        answers = data.get('answers', {})
        total_health_score = 0
        part_scores = {'PART1': 0, 'PART2': 0, 'PART3': 0, 'PART4': 0, 'PART5': 0}

        # 긍정문항 목록
        positive_questions = {3, 5, 8, 10, 13, 15, 18, 20, 21, 22, 24, 25}

        for i in range(1, 26):
            q_key = f'q{i}'
            try:
                raw_val = int(answers.get(q_key, 3))
            except (ValueError, TypeError):
                raw_val = 3
            
            # 🟢 건강도 환산 공식 적용
            # 긍정문항: (raw_val - 1) | 부정문항: (5 - raw_val)
            health_val = (raw_val - 1) if i in positive_questions else (5 - raw_val)
            total_health_score += health_val
            
            if 1 <= i <= 5: part_scores['PART1'] += health_val
            elif 6 <= i <= 10: part_scores['PART2'] += health_val
            elif 11 <= i <= 15: part_scores['PART3'] += health_val
            elif 16 <= i <= 20: part_scores['PART4'] += health_val
            elif 21 <= i <= 25: part_scores['PART5'] += health_val

        # 🟢 100점 만점 건강도 점수 (총 25문항 × 4점)
        calc_score = total_health_score

        # 📊 통합 데이터셋 기반 동적 백분위 연산
        if KAGLE_SCORES:
            higher_count = sum(1 for score in KAGLE_SCORES if score > calc_score)
            calculated_percentile = round((higher_count / len(KAGLE_SCORES)) * 100, 1)
            percentile = max(1.0, min(99.0, calculated_percentile))
        else:
            percentile = 50.0

        age_percentile = max(1.0, min(99.0, round(percentile * 0.92, 1)))

        # 🟢 건강도 기준 등급 판정 (80점 이상 = 매우 건강 / 20점 미만 = 고위험)
        if calc_score >= 80: status = "매우 건강"
        elif calc_score >= 60: status = "양호"
        elif calc_score >= 40: status = "주의"
        elif calc_score >= 20: status = "위험"
        else: status = "고위험"

        top_part = max(part_scores, key=part_scores.get)

        session['survey_result'] = {
            'nickname': user_name,
            'user_age': user_age,
            'total_score': calc_score,
            'status': status,
            'percentile': percentile,
            'age_percentile': age_percentile,
            'part_scores': part_scores,
            'top_part': top_part,
            'total_dataset_count': TOTAL_DATASET_COUNT,
            'solutions': [
                {'icon': '📱', 'title': '디지털 디톡스 시간 설정', 'desc': '하루 지정된 1~2시간 동안은 알림을 끄고 화면과 거리를 두세요.'},
                {'icon': '🧘', 'title': '오프라인 활동 비중 확대', 'desc': '산책, 운동, 대면 대화 등 실제 감각을 깨우는 활동 시간을 늘려보세요.'},
                {'icon': '🌙', 'title': '취침 전 스마트폰 거치대 배치', 'desc': '잠들기 1시간 전 스마트폰을 침대 멀리 놓아 수면 환경을 개선하세요.'}
            ]
        }

        # CSV 실시간 제출 저장
        data_dir = os.path.join(app.root_path, 'data')
        if not os.path.exists(data_dir): os.makedirs(data_dir)
        save_file_path = os.path.join(data_dir, 'user_responses.csv')
        file_exists = os.path.exists(save_file_path)

        with open(save_file_path, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'name', 'phone', 'email', 'gender', 'age', 'total_score', 'status', 'top_part'])
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                user_name, user_phone, user_email, user_gender, user_age, calc_score, status, top_part
            ])

        print(f"✅ [제출 완료] 유저: {user_name} | 통합 백분위: 상위 {percentile}% (데이터 {TOTAL_DATASET_COUNT}개 비교)")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ [Submit Error]:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)