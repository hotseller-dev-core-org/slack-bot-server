# Slack Bot Server

Slack 채널의 입금 메시지를 자동 파싱 및 처리하고, 응답 메시지 전송과 이모지 반응을 통해 결과를 시각적으로 피드백하는 FastAPI 기반 서버입니다. 중복 이벤트 처리 방지를 위해 Redis를 사용합니다.

---

## 🧩 주요 기능

- Slack 메시지 수신 및 이벤트 핸들링 (`/v1/slack/event`)
- 입금 메시지 자동 파싱 및 외부 API 연동
- 응답 메시지 및 결과 이모지(`✅`, `❌`) 자동 전송
- Redis 기반 이벤트 중복 처리 방지 (`event_id` 기준)

---

## 🗂️ 디렉토리 구조

```
.
├── app.py / main.py              # FastAPI 앱 진입점
├── slack_bot/
│   ├── api/
│   │   ├── deposit_check.py      # 메시지 파싱 및 처리 로직
│   │   └── router.py             # Slack Event & Action 핸들러
│   ├── manager.py                # 이벤트/액션 매니저 (확장 가능)
│   ├── slack.py                  # Slack API 래퍼
│   └── utils.py                  # 유틸 함수 모음
├── common/
│   ├── config.py                 # 설정 및 환경변수 관리
│   ├── logger.py                 # 로깅 설정
│   └── module.py                 # Redis 클라이언트 (Simple or Async)
├── gunicorn.conf.py             # (Optional) Gunicorn 설정
├── requirements.txt
└── README.md
```

---

## ⚙️ 설치 및 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성하여 다음 항목을 정의합니다:

```env
SLACK_APP_TOKEN=xoxb-...
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=your_password
REDIS_DB=0
```

또는 `common/config.py`에서 직접 JSON 파싱:

```python
REDIS = {
    "host": "127.0.0.1",
    "port": 6379,
    "password": "your_password",
    "databases": [0]
}
```

### 3. 서버 실행

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

(운영 환경에서는 `gunicorn` + `uvicorn.workers.UvicornWorker` 조합 권장)

---

## 🚀 배포 전 체크리스트

- [x] Slack App 이벤트 수신 URL을 `/v1/slack/event`로 설정
- [x] 다음 Slack 권한 부여 완료
  - `chat:write`
  - `reactions:write`
  - `channels:history` 또는 `groups:history`
- [x] Redis 연결 및 중복 방지 키 TTL 설정 완료

---

## 🔁 이벤트 중복 처리 방식

- Slack 이벤트의 `event_id` 값을 기준으로 Redis에 `slack_event:{event_id}` 키를 5분간 저장
- 이후 동일한 이벤트가 다시 들어오면 무시하고 처리하지 않음

```python
# Redis Key 예시
slack_event:Ev08U1XXXXXX
```

---

## 📡 API Endpoints

| 메서드 | URL                  | 설명                     |
|--------|----------------------|--------------------------|
| POST   | `/v1/slack/event`    | Slack Event 수신 처리     |
| POST   | `/v1/slack/action`   | Slack Block Action 처리   |

---

## 👨‍💻 개발자 참고

- 로그는 `common/logger.py`를 통해 `traceloggerx` 유틸리티 기반 로그로 출력됩니다.
- `aio_log_method_call` 데코레이터로 비동기 함수 호출 시 로그 자동 기록됩니다.
- 슬랙 메시지 전송, 반응 처리 등은 `slack_bot/slack.py` 내부 `SlackAPI` 클래스를 사용합니다.

