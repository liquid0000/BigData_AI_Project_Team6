document.addEventListener('DOMContentLoaded', () => {
    const surveyForm = document.getElementById('surveyForm');
    if (!surveyForm) return;

    const STORAGE_KEY = 'sns_survey_temp_data';
    let isSubmitting = false;

    // 1. 저장된 임시 데이터가 있으면 자동으로 불러와서 체크
    const savedData = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    Object.keys(savedData).forEach(qName => {
        const value = savedData[qName];
        const radio = surveyForm.querySelector(`input[name="${qName}"][value="${value}"]`);
        if (radio) radio.checked = true;
    });

    // 2. 사용자가 선택을 바꿀 때마다 LocalStorage에 실시간 저장
    surveyForm.addEventListener('change', (e) => {
        if (e.target.type === 'radio') {
            const currentData = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
            currentData[e.target.name] = e.target.value;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(currentData));
        }
    });

    // 3. 페이지 이탈(뒤로가기, 탭 닫기, 새로고침 등) 시 경고창 표시
    window.addEventListener('beforeunload', (e) => {
        // 정상 제출 중이 아니고, 작성 중인 데이터가 있을 때만 경고
        const hasData = Object.keys(JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')).length > 0;
        if (!isSubmitting && hasData) {
            e.preventDefault();
            e.returnValue = ''; // 브라우저 표준 이탈 경고 출력
        }
    });

    // 4. 설문 제출 처리
    surveyForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        isSubmitting = true; // 정상 제출 상태로 변경 (경고창 차단)

        const formData = new FormData(surveyForm);
        const responseData = {};

        formData.forEach((value, key) => {
            responseData[key] = parseInt(value, 10);
        });

        try {
            const response = await fetch('/api/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(responseData)
            });

            if (response.ok) {
                // 제출 성공 시 임시 저장 데이터 삭제
                localStorage.removeItem(STORAGE_KEY);
                window.location.href = '/result';
            } else {
                alert('제출 중 오류가 발생했습니다. 다시 시도해주세요.');
                isSubmitting = false;
            }
        } catch (error) {
            console.error('Error submitting survey:', error);
            alert('서버와의 통신에 실패했습니다.');
            isSubmitting = false;
        }
    });
});