from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import numpy as np

app = Flask(__name__)
app.secret_key = 'sns_psychology_secret_key'  # 세션 관리를 위한 비밀키

# ---------------------------------------------------------
# 1. 문항 및 척도 설정
# ---------------------------------------------------------
# 🟢 긍정 문항 (1-based index): Q3, Q5, Q8, Q10, Q13, Q15, Q18, Q20, Q21, Q22, Q24, Q25
POSITIVE_QUESTIONS = {3, 5, 8, 10, 13, 15, 18, 20, 21, 22, 24, 25}

# ---------------------------------------------------------
# 2. 메인/설문/결과 페이지 라우팅
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/survey')
def survey():
    return render_template('survey.html')

@app.route('/result')
def result():
    return render_template('result.html')

# ---------------------------------------------------------
# 3. 진단 점수 및 백분위 계산 API
# ---------------------------------------------------------
@app.route('/api/diagnose', methods=['POST'])
def diagnose():
    data = request.get_json()
    
    # 전달받는 데이터
    user_info = data.get('user_info', {})  # { name, age_group, gender, email, phone }
    answers = data.get('answers', [])      # 25개 응답 리스트 (각 1~5점)
    
    if len(answers) != 25:
        return jsonify({'error': '25개 문항에 모두 응답해야 합니다.'}), 400

    # --- [Step 1] 문항별 건강도 점수 계산 (영역별 집계 포함) ---
    part_scores = [0, 0, 0, 0, 0]  # Part 1~5 각각 20점 만점
    total_health_score = 0

    for i, response in enumerate(answers, start=1):
        score = int(response)
        
        if i in POSITIVE_QUESTIONS:
            # 🟢 긍정 문항: (응답점수 - 1) ➔ 5점: +4점, 1점: +0점
            item_score = score - 1
        else:
            # 🔴 부정 문항: (5 - 응답점수) ➔ 1점: +4점, 5점: +0점
            item_score = 5 - score
            
        total_health_score += item_score
        
        # 영역별 점수 합산 (5문항씩 하나의 Part, 각 20점 만점)
        part_idx = (i - 1) // 5
        part_scores[part_idx] += item_score

    # --- [Step 2] 5단계 심리 건강 상태 분류 ---
    # 0점(극도로 위험) ~ 100점(매우 건강)
    if total_health_score >= 81:
        status = "매우 건강"
    elif total_health_score >= 61:
        status = "양호"
    elif total_health_score >= 41:
        status = "보통"
    elif total_health_score >= 21:
        status = "주의군"
    else:
        status = "고위험군 (극도로 위험)"

    # --- [Step 3] 백분위 연산 (외부 데이터셋 기준 모의 연산 예시) ---
    # TODO: 추후 MongoDB 및 PySpark 파이프라인 연동 부분
    # 현재는 총점에 기반한 백분위 모의 산출 (건강도 점수가 높을수록 상위 백분위)
    overall_percentile = round((total_health_score / 100) * 100, 1)
    age_group_percentile = round(min(100.0, overall_percentile * 1.05), 1)  # 연령대 비교 예시

    # --- [Step 4] 반환 객체 생성 ---
    result_data = {
        'user_info': user_info,
        'total_health_score': total_health_score,  # 0 ~ 100점
        'status': status,
        'part_scores': {
            'part1': part_scores[0],  # 이용 습관 및 의존도 (0~20점)
            'part2': part_scores[1],  # 타인 비교 및 자존감 (0~20점)
            'part3': part_scores[2],  # 정서 및 감정 상태 (0~20점)
            'part4': part_scores[3],  # 통제력 및 FOMO (0~20점)
            'part5': part_scores[4]   # 신체 영향 및 대인관계 (0~20점)
        },
        'percentiles': {
            'overall': overall_percentile,
            'age_group': age_group_percentile
        }
    }

    return jsonify(result_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)