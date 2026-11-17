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

# 🟢 사용자 등록 및 기존 전화번호 조회 (기존 번호면 바로 결과창으로 이동)
@app.route('/api/start-user', methods=['POST'])
def start_user():
    data = request.json or {}
    phone = (data.get('phone') or '').strip()
    name = (data.get('name') or '').strip()
    email = data.get('email')
    age_group = data.get('ageGroup')
    gender = data.get('gender')
    
    # 기존 전화번호 확인
    existing = db.find_user(phone)
    if existing:
        updated_name = name if name else existing.get('name')
        updated_age = age_group if age_group else existing.get('age_group')
        updated_gender = gender if gender else existing.get('gender')

        # 새 입력값이 있으면 DB 프로필 최신화
        db.users.update_one(
            {'phone': phone},
            {'$set': {
                'name': updated_name,
                'age_group': updated_age,
                'gender': updated_gender
            }}
        )

        user_info = {
            'phone': existing.get('phone'),
            'name': updated_name,
            'email': existing.get('email'),
            'ageGroup': updated_age,
            'gender': updated_gender
        }

        # 저장된 진단 결과가 없으면 기본 결과 객체 구성 (예전 테스트 계정 호환)
        last_result = existing.get('last_result') or {
            'calc_score': 50,
            'health_status': '주의',
            'part_scores': {'PART1': 10, 'PART2': 10, 'PART3': 10, 'PART4': 10, 'PART5': 10}
        }

        return jsonify({
            'status': 'success',
            'is_existing': True,
            'userInfo': user_info,
            'resultData': last_result
        })

    # 신규 사용자 저장
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
        'userInfo': user_info,
        'resultData': None
    })

# 🟢 설문 제출 및 건강도 계산 API
@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json or {}
    user_info = data.get('userInfo', {})
    answers = data.get('answers', {})
    phone = (user_info.get('phone') or '').strip()

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

    # 해당 전화번호 사용자 문서에 최신 진단 결과 저장
    if phone:
        db.users.update_one(
            {'phone': phone},
            {'$set': {'last_result': result_payload}}
        )

    return jsonify({
        'status': 'success',
        'calc_score': calc_score,
        'health_status': status,
        'part_scores': part_scores
    })

if __name__ == '__main__':
    app.run(debug=True)