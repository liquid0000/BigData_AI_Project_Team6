// 1. 사전 정보 입력 및 60일 재진단 기한 검증 (API 호출)
function startSurvey() {
    const userInfo = {
        nickname: document.getElementById('nickname').value.trim(),
        phone: document.getElementById('phone').value.trim(),
        email: document.getElementById('email').value.trim(),
        age_group: document.getElementById('ageGroup').value,
        gender: document.getElementById('gender').value
    };

    if (!userInfo.nickname || !userInfo.phone || !userInfo.email || !userInfo.age_group) {
        alert("모든 필수 항목을 입력해 주세요.");
        return;
    }

    // 백엔드로 60일 검증 요청
    fetch('/api/check-user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: userInfo.phone, email: userInfo.email })
    })
        .then(res => res.json())
        .then(data => {
            if (data.can_survey) {
                sessionStorage.setItem('user_info', JSON.stringify(userInfo));
                window.location.href = '/survey';
            } else {
                alert(data.message);
            }
        })
        .catch(err => {
            console.error("API 요청 실패:", err);
            alert("서버 통신 중 오류가 발생했습니다.");
        });
}

// 2. '진단 완료' 클릭 시 백엔드로 API 요청 전송
function submitSurvey() {
    const userInfo = JSON.parse(sessionStorage.getItem('user_info'));
    if (!userInfo) {
        alert("사전 정보가 없습니다. 메인 페이지로 이동합니다.");
        window.location.href = '/';
        return;
    }

    const formData = new FormData(document.getElementById('surveyForm'));
    const answers = {};
    formData.forEach((value, key) => answers[key] = value);

    // Q4 ~ Q17 14개 필수 라디오버튼 체킹 검증
    for (let i = 4; i <= 17; i++) {
        if (!answers[`Q${i}`]) {
            alert(`Q${i}번 문항에 응답해 주세요.`);
            return;
        }
    }

    // 백엔드로 최종 응답 데이터 제출 (커밋 포인트)
    fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_info: userInfo, answers: answers })
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                sessionStorage.setItem('result_data', JSON.stringify(data.result));
                window.location.href = '/result';
            } else {
                alert("제출 처리 실패: " + (data.message || "오류 발생"));
            }
        })
        .catch(err => {
            console.error("제출 실패:", err);
            alert("서버 제출 중 오류가 발생했습니다.");
        });
}