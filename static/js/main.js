document.addEventListener('DOMContentLoaded', () => {
    const INFO_STORAGE_KEY = 'sns_survey_userInfo';
    const SURVEY_STORAGE_KEY = 'sns_survey_temp_data';

    // ==========================================
    // 1. 사전 정보 입력 페이지 (index.html) 로직
    // ==========================================
    const infoForm = document.getElementById('infoForm');
    if (infoForm) {
        // 이미 저장된 사전 정보가 있다면 input에 복원
        const savedInfo = JSON.parse(localStorage.getItem(INFO_STORAGE_KEY) || '{}');
        if (savedInfo.nickname) document.getElementById('nickname').value = savedInfo.nickname;
        if (savedInfo.phone) document.getElementById('phone').value = savedInfo.phone;
        if (savedInfo.email) document.getElementById('email').value = savedInfo.email;
        if (savedInfo.ageGroup) document.getElementById('ageGroup').value = savedInfo.ageGroup;
        if (savedInfo.gender) document.getElementById('gender').value = savedInfo.gender;

        // '진단 시작하기' 버튼/링크 클릭 시 입력값 검증 및 저장 후 이동
        const startBtn = infoForm.querySelector('a.btn-primary') || infoForm.querySelector('button');
        if (startBtn) {
            startBtn.addEventListener('click', (e) => {
                const nickname = document.getElementById('nickname').value.trim();
                const phone = document.getElementById('phone').value.trim();
                const email = document.getElementById('email').value.trim();
                const ageGroup = document.getElementById('ageGroup').value;
                const gender = document.getElementById('gender').value;

                // 필수 입력 항목 검증
                if (!nickname || !phone || !email || !ageGroup || !gender) {
                    e.preventDefault();
                    alert('모든 사전 정보를 입력 및 선택해 주세요.');
                    return;
                }

                // 입력된 사전 정보 LocalStorage 저장
                const userInfo = { nickname, phone, email, ageGroup, gender };
                localStorage.setItem(INFO_STORAGE_KEY, JSON.stringify(userInfo));
            });
        }
    }

    // ==========================================
    // 2. 설문 진행 페이지 (survey.html) 로직
    // ==========================================
    const surveyForm = document.getElementById('surveyForm');
    if (!surveyForm) return; // 설문 페이지가 아닌 경우 이하 중단

    let isSubmitting = false;

    // A. 저장된 설문 임시 데이터가 있으면 자동으로 불러와서 체크
    const savedData = JSON.parse(localStorage.getItem(SURVEY_STORAGE_KEY) || '{}');
    Object.keys(savedData).forEach(qName => {
        const value = savedData[qName];
        const radio = surveyForm.querySelector(`input[name="${qName}"][value="${value}"]`);
        if (radio) radio.checked = true;
    });

    // B. 사용자가 선택을 바꿀 때마다 LocalStorage에 실시간 저장 (튕김/새로고침 대응)
    surveyForm.addEventListener('change', (e) => {
        if (e.target.type === 'radio') {
            const currentData = JSON.parse(localStorage.getItem(SURVEY_STORAGE_KEY) || '{}');
            currentData[e.target.name] = e.target.value;
            localStorage.setItem(SURVEY_STORAGE_KEY, JSON.stringify(currentData));
        }
    });

    // C. 페이지 이탈(뒤로가기, 탭 닫기, 새로고침 등) 시 경고창 표시
    window.addEventListener('beforeunload', (e) => {
        const hasData = Object.keys(JSON.parse(localStorage.getItem(SURVEY_STORAGE_KEY) || '{}')).length > 0;
        if (!isSubmitting && hasData) {
            e.preventDefault();
            e.returnValue = ''; // 브라우저 표준 이탈 경고 출력
        }
    });

    // D. 설문 최종 제출 처리 (사전 정보 + 25문항 응답 함께 전송)
    surveyForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        isSubmitting = true; // 정상 제출 상태로 변경 (경고창 차단)

        // 사전 정보 가져오기
        const userInfo = JSON.parse(localStorage.getItem(INFO_STORAGE_KEY) || '{}');

        // 25개 설문 답변 추출 (0~4 정수 변환)
        const formData = new FormData(surveyForm);
        const surveyAnswers = {};
        formData.forEach((value, key) => {
            surveyAnswers[key] = parseInt(value, 10);
        });

        // 백엔드 전송용 통합 데이터 구조 생성
        const payload = {
            userInfo: userInfo,
            answers: surveyAnswers
        };

        try {
            const response = await fetch('/api/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                // 제출 성공 시 임시 저장된 데이터 삭제
                localStorage.removeItem(SURVEY_STORAGE_KEY);
                localStorage.removeItem(INFO_STORAGE_KEY);
                window.location.href = '/result';
            } else {
                alert('제출 중 오류가 발생했습니다. 다시 시도해 주세요.');
                isSubmitting = false;
            }
        } catch (error) {
            console.error('Error submitting survey:', error);
            alert('서버와의 통신에 실패했습니다.');
            isSubmitting = false;
        }
    });
});