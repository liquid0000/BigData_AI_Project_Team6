let isSurveyCompleted = false;

document.addEventListener('DOMContentLoaded', () => {
    const surveyForm = document.getElementById('surveyForm');
    const startForm = document.getElementById('startForm');

    // ==========================================
    // 1. index.html - 사용자 정보 세션 저장
    // ==========================================
    if (startForm) {
        startForm.addEventListener('submit', (e) => {
            e.preventDefault();
            isSurveyCompleted = true; // 페이지 이동 시 경고창 차단

            const name = document.getElementById('userName')?.value || '';
            const phone = document.getElementById('userPhone')?.value || '';
            const email = document.getElementById('userEmail')?.value || '';
            const genderElem = document.querySelector('input[name="userGender"]:checked');
            const gender = genderElem ? genderElem.value : '';

            sessionStorage.setItem('userName', name);
            sessionStorage.setItem('userPhone', phone);
            sessionStorage.setItem('userEmail', email);
            sessionStorage.setItem('userGender', gender);

            window.location.href = '/survey';
        });
    }

    // ==========================================
    // 2. survey.html - 임시 저장 및 최종 제출
    // ==========================================
    if (surveyForm) {
        // 복구 로직
        const savedAnswers = JSON.parse(localStorage.getItem('temp_sns_answers') || '{}');
        for (const [qName, val] of Object.entries(savedAnswers)) {
            const input = document.querySelector(`input[name="${qName}"][value="${val}"]`);
            if (input) input.checked = true;
        }

        const savedAge = localStorage.getItem('temp_ageGroup');
        if (savedAge && document.getElementById('ageGroup')) {
            document.getElementById('ageGroup').value = savedAge;
        }

        // 실시간 저장
        surveyForm.addEventListener('change', (e) => {
            if (e.target.type === 'radio') {
                const answers = JSON.parse(localStorage.getItem('temp_sns_answers') || '{}');
                answers[e.target.name] = e.target.value;
                localStorage.setItem('temp_sns_answers', JSON.stringify(answers));
            } else if (e.target.id === 'ageGroup') {
                localStorage.setItem('temp_ageGroup', e.target.value);
            }
        });

        // 설문 제출
        surveyForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const ageGroup = document.getElementById('ageGroup')?.value;
            if (!ageGroup) {
                alert('나이(연령대)를 선택해 주세요!');
                document.getElementById('ageGroup')?.focus();
                return;
            }

            const formData = new FormData(surveyForm);
            const answers = {};
            formData.forEach((value, key) => {
                if (key.startsWith('q')) answers[key] = value;
            });

            if (Object.keys(answers).length < 25) {
                alert('아직 응답하지 않은 문항이 있습니다. 모든 문항에 답변해 주세요!');
                return;
            }

            const payload = {
                userInfo: {
                    name: sessionStorage.getItem('userName') || '사용자',
                    phone: sessionStorage.getItem('userPhone') || '',
                    email: sessionStorage.getItem('userEmail') || '',
                    gender: sessionStorage.getItem('userGender') || '',
                    ageGroup: ageGroup
                },
                answers: answers
            };

            try {
                const response = await fetch('/api/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();

                if (result.status === 'success') {
                    isSurveyCompleted = true;
                    localStorage.removeItem('temp_sns_answers');
                    localStorage.removeItem('temp_ageGroup');
                    window.location.href = '/result';
                } else {
                    alert('제출 중 오류가 발생했습니다: ' + result.message);
                }
            } catch (err) {
                console.error('Error:', err);
                alert('서버와의 통신에 실패했습니다.');
            }
        });
    }
});

// ==========================================
// 3. 새로고침 및 브라우저 이탈 방지
// ==========================================
window.addEventListener('beforeunload', (e) => {
    const surveyForm = document.getElementById('surveyForm');
    if (surveyForm && !isSurveyCompleted) {
        e.preventDefault();
        e.returnValue = '';
    }
});