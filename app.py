from flask import Flask, render_template, request, jsonify
import db

app = Flask(__name__)

# MongoDB 인덱스 준비 (연락처 중복 방지, 개인정보 60일 자동 삭제)
db.init_db()

def estimate_top_percentile(score, stats_doc):
    """Spark가 계산한 25th, median(50th), 75th 사분위수를 이용해 상위 % 추정"""
    if not stats_doc:
        return None

    p25 = stats_doc.get("25th_percentile")
    p50 = stats_doc.get("median")
    p75 = stats_doc.get("75th_percentile")

    if p25 is None or p50 is None or p75 is None:
        return None

    # 점수가 높을수록 상위 % 숫자가 작아짐 (p75 이상 = 상위 25% 이내)
    if score >= p75:
        ratio = (100 - score) / max(1, (100 - p75))
        top_pct = round(1 + ratio * 24)
    elif score >= p50:
        ratio = (p75 - score) / max(1, (p75 - p50))
        top_pct = round(25 + ratio * 25)
    elif score >= p25:
        ratio = (p50 - score) / max(1, (p50 - p25))
        top_pct = round(50 + ratio * 25)
    else:
        ratio = (p25 - score) / max(1, p25)
        top_pct = round(75 + ratio * 24)

    return max(1, min(99, top_pct))

def calculate_percentiles(calc_score, age_group):
    """MongoDB spark_results 컬렉션에서 Spark 집계 결과를 읽어 전체/연령대 백분위 반환"""
    spark_col = db.db["spark_results"]
    all_doc = spark_col.find_one({"age_group": "ALL"})
    age_doc = spark_col.find_one({"age_group": age_group}) if age_group else None

    fallback = max(1, min(99, 100 - calc_score))

    overall_pct = estimate_top_percentile(calc_score, all_doc)
    age_pct = estimate_top_percentile(calc_score, age_doc)

    if all_doc and all_doc.get("count"):
        total_count = all_doc["count"]
    else:
        all_age_docs = list(spark_col.find({}, {"count": 1}))
        total_count = sum(d.get("count", 0) for d in all_age_docs) or None

    final_overall = overall_pct if overall_pct is not None else (age_pct if age_pct is not None else fallback)
    final_age = age_pct if age_pct is not None else final_overall

    return final_overall, final_age, total_count

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/survey')
def survey():
    return render_template('survey.html')

@app.route('/result')
def result():
    return render_template('result.html')

@app.route('/api/start-user', methods=['POST'])
def start_user():
    data = request.json or {}
    phone = (data.get('phone') or '').strip()
    name = (data.get('name') or '').strip()
    email = data.get('email')
    age_group = data.get('ageGroup')
    gender = data.get('gender')
    
    existing = db.find_user(phone)
    if existing:
        updated_name = name if name else existing.get('name')
        updated_age = age_group if age_group else existing.get('age_group')
        updated_gender = gender if gender else existing.get('gender')

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

        last_result = existing.get('last_result') or {
            'calc_score': 50,
            'health_status': '주의',
            'part_scores': {'PART1': 10, 'PART2': 10, 'PART3': 10, 'PART4': 10, 'PART5': 10}
        }

        p_all, p_age, ds_count = calculate_percentiles(last_result.get('calc_score', 50), updated_age)
        last_result['percentile'] = p_all
        last_result['age_percentile'] = p_age
        if ds_count:
            last_result['total_dataset_count'] = ds_count

        return jsonify({
            'status': 'success',
            'is_existing': True,
            'userInfo': user_info,
            'resultData': last_result
        })

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

@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json or {}
    user_info = data.get('userInfo', {})
    answers = data.get('answers', {})
    phone = (user_info.get('phone') or '').strip()
    age_group = user_info.get('ageGroup')

    total_health_score = 0
    part_scores = {'PART1': 0, 'PART2': 0, 'PART3': 0, 'PART4': 0, 'PART5': 0}
    positive_questions = {3, 5, 8, 10, 13, 15, 18, 20, 21, 22, 24, 25}

    for i in range(1, 26):
        q_key = f'q{i}'
        try:
            raw_val = int(answers.get(q_key, 3))
        except (ValueError, TypeError):
            raw_val = 3
        
        health_val = (raw_val - 1) if i in positive_questions else (5 - raw_val)
        total_health_score += health_val

        if 1 <= i <= 5: part_scores['PART1'] += health_val
        elif 6 <= i <= 10: part_scores['PART2'] += health_val
        elif 11 <= i <= 15: part_scores['PART3'] += health_val
        elif 16 <= i <= 20: part_scores['PART4'] += health_val
        elif 21 <= i <= 25: part_scores['PART5'] += health_val

    calc_score = total_health_score

    if calc_score >= 80: status = "매우 건강"
    elif calc_score >= 60: status = "양호"
    elif calc_score >= 40: status = "주의"
    elif calc_score >= 20: status = "위험"
    else: status = "고위험"

    p_all, p_age, ds_count = calculate_percentiles(calc_score, age_group)

    result_payload = {
        'calc_score': calc_score,
        'health_status': status,
        'part_scores': part_scores,
        'percentile': p_all,
        'age_percentile': p_age,
        'total_dataset_count': ds_count
    }

    db.save_response(
        age_group,
        user_info.get('gender'),
        answers,
        part_scores,
        calc_score,
        status
    )

    if phone:
        db.users.update_one(
            {'phone': phone},
            {'$set': {'last_result': result_payload}}
        )

    return jsonify({
        'status': 'success',
        **result_payload
    })

if __name__ == '__main__':
    app.run(debug=True)