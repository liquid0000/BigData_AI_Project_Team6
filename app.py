from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)
DB_NAME = 'sns_health.db'

# 🟢 DB 테이블 초기화
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            age_group TEXT,
            gender TEXT,
            score INTEGER,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/survey')
def survey():
    return render_template('survey.html')

@app.route('/result')
def result():
    return render_template('result.html')

# 🟢 [신규 API] 사용자 등록 및 기존 사용자 자동 조회 (이어하기)
@app.route('/api/start-user', methods=['POST'])
def start_user():
    data = request.json or {}
    phone = data.get('phone')
    
    if not phone:
        return jsonify({'status': 'error', 'message': '연락처가 필요합니다.'}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 기존 사용자 확인
    cursor.execute('SELECT phone, name, email, age_group, gender FROM users WHERE phone = ?', (phone,))
    existing_user = cursor.fetchone()

    if existing_user:
        # DB에 기존 정보가 있다면 기존 데이터 반환
        user_info = {
            'phone': existing_user[0],
            'name': existing_user[1],
            'email': existing_user[2],
            'ageGroup': existing_user[3],
            'gender': existing_user[4]
        }
        conn.close()
        return jsonify({'status': 'success', 'is_existing': True, 'userInfo': user_info})

    # 신규 사용자 DB 저장
    name = data.get('name')
    email = data.get('email')
    age_group = data.get('ageGroup')
    gender = data.get('gender')

    cursor.execute('''
        INSERT INTO users (phone, name, email, age_group, gender)
        VALUES (?, ?, ?, ?, ?)
    ''', (phone, name, email, age_group, gender))
    
    conn.commit()
    conn.close()

    user_info = {
        'phone': phone,
        'name': name,
        'email': email,
        'ageGroup': age_group,
        'gender': gender
    }
    return jsonify({'status': 'success', 'is_existing': False, 'userInfo': user_info})

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

    # DB에 점수 및 결과 업데이트
    if phone:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET score = ?, status = ? WHERE phone = ?', (calc_score, status, phone))
        conn.commit()
        conn.close()

    return jsonify({
        'status': 'success',
        'calc_score': calc_score,
        'health_status': status,
        'part_scores': part_scores
    })

if __name__ == '__main__':
    app.run(debug=True)