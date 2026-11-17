from flask import Flask, render_template, request, jsonify
import db

app = Flask(__name__)

# MongoDB 인덱스 준비 (연락처 중복 방지, 개인정보 60일 자동 삭제)
db.init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/survey')
def survey():
    return render_template('survey.html')

@app.route('/result')
def result():
    return render_template('result.html')

# 🟢 [신규 API] 사용자 등록 및 기존 사용자 자동 조회 (이어하기 및 기존 결과 불러오기)
@app.route('/api/start-user', methods=['POST'])
def start_user():
    data = request.json or {}
    phone = data.get('phone')
    
    # 기존 사용자 확인
    existing = db.find_user(phone)
    if existing:
        user_info = {
            'phone': existing.get('phone'),
            'name': existing.get('name'),
            'email': existing.get('email'),
            'ageGroup': existing.get('age_group'),
            'gender': existing.get('gender')
        }
        # 이미 완료된 진단 결과가 저장되어 있는지 확인
        last_result = existing.get('last_result')
        return jsonify({
            'status': 'success',
            'is_existing': True,
            'has_result': bool(last_result),
            'userInfo': user_info,
            'resultData': last_result
        })

    # 신규 사용자 저장
    name = data.get('name')
    email = data.get('email')
    age_group = data.get('ageGroup')
    gender = data.get('gender')
    db.create_user(phone, name, email, age_group, gender, data.get('guardianInfo'))

    user_info = {
        'phone': phone,
        'name': name,
        'email': email,
        'ageGroup': age_group,
        'gender': gender
    }
    return jsonify({
        'status': 'success',
        'is_existing': False,
        'has_result': False,
        'userInfo': user_info,
        'resultData': None
    })

# 🟢 설문 제출 및 건강도 계산 API
@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json or {}
    user_info = data.get('userInfo', {})
    answers = data.get('answers', {})
    phone = user_info.get('phone')

    total_health_score = 0
    part_scores = {'PART1': 0, 'PART2': 0, 'PART3': 0, 'PART4': 0, 'PART5': 0}
    positive_questions = {3, 5, 8, 10, 13, 15, 18, 20, 21, 22, 24, 25}

    for i in range(1, 26):
        q_key = f'q{i}'
        try:
            raw_val = int(answers.get(q_key, 3))
        except (ValueError, TypeError):
            raw_val = 3
        
        # 100점 만점 역채점 연산
        health_val = (raw_val - 1) if i in positive_questions else (5 - raw_val)
        total_health_score += health_val

        if 1 <= i <= 5: part_scores['PART1'] += health_val
        elif 6 <= i <= 10: part_scores['PART2'] += health_val
        elif 11 <= i <= 15: part_scores['PART3'] += health_val
        elif 16 <= i <= 20: part_scores['PART4'] += health_val
        elif 21 <= i <= 25: part_scores['PART5'] += health_val

    calc_score = total_health_score

    # 건강도 등급 판정
    if calc_score >= 80: status = "매우 건강"
    elif calc_score >= 60: status = "양호"
    elif calc_score >= 40: status = "주의"
    elif calc_score >= 20: status = "위험"
    else: status = "고위험"

    result_payload = {
        'calc_score': calc_score,
        'health_status': status,
        'part_scores': part_scores
    }

    # 응답 및 점수를 익명으로 저장 (통계용)
    db.save_response(
        user_info.get('ageGroup'),
        user_info.get('gender'),
        answers,
        part_scores,
        calc_score,
        status
    )

    # 기존 사용자 조회 시 바로 결과를 불러올 수 있도록 사용자 문서에도 최신 결과 업데이트
    if phone and hasattr(db, 'users_col'):
        db.users_col.update_one({'phone': phone}, {'$set': {'last_result': result_payload}})
    elif phone and hasattr(db, 'users'):
        db.users.update_one({'phone': phone}, {'$set': {'last_result': result_payload}})

    return jsonify({
        'status': 'success',
        'calc_score': calc_score,
        'health_status': status,
        'part_scores': part_scores
    })

if __name__ == '__main__':
    app.run(debug=True)