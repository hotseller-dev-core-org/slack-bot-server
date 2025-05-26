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

## 환경 설정

### 테스트/운영 모드 전환

환경변수 `SLACK_BOT_TEST_MODE`를 통해 테스트/운영 모드를 전환할 수 있습니다.

#### 테스트 모드 활성화
```bash
export SLACK_BOT_TEST_MODE=true
```

#### 운영 모드 (기본값)
```bash
export SLACK_BOT_TEST_MODE=false
# 또는 환경변수 설정하지 않음
```

### 채널 및 API 설정

#### 테스트 모드
- **모든 채널**: `C06MFPLN81W` (통합 테스트 채널)
- **API URLs**:
  - HOT_AUTO: `http://10.0.23.222/api/point`
  - SNS_TOOL: `https://api.snstool.co.kr/api/point`
  - HOT_PARTNERS: `https://api.self-marketing-platform.co.kr/api/payment/deposit`
  - JAPAN_SMS: `https://api.self-marketing-platform.co.kr/api/payment/deposit`

#### 운영 모드
- **채널별 설정**:
  - HOT_AUTO: `C025V0PJZ1P`
  - SNS_TOOL: `C08CHA1TZQW`
  - MONEYCOON: `C0376RS8KLZ`
  - JAPAN_NIHON: `C05LS9VF5DY`
  - JAPAN_TOMO: `C06C3HG1Q0K`
  - JAPAN_FOLLOWERLAB: `C08F10YTBKK`
  - HOT_PARTNERS: `C08BR1P920H`
  - SMS: `C05NYEWHK1S`

- **API URLs**:
  - HOT_AUTO: `http://10.0.23.222/api/point`
  - SNS_TOOL: `https://api.snstool.co.kr/api/point`
  - HOT_PARTNERS: `https://api.hotpartners.co.kr/partner/point/auto-charge`
  - JAPAN_SMS: `http://10.0.2.21/api/payment/deposit`

## 테스트 방법

### 1. 테스트 모드에서 모든 서비스 테스트
```bash
# 테스트 모드 활성화
export SLACK_BOT_TEST_MODE=true

# 서버 재시작
python main.py
```

### 2. 테스트 채널에서 다양한 메시지 형식 테스트

#### 표준 메시지 (HOT_AUTO, SNS_TOOL, HOT_PARTNERS)
```
2025/05/26 19:00 입금 50,000원 테스트유저
```

#### 일본 채널 메시지
```
니혼 입금 2025/05/26 19:00 테스트 메시지
토모 입금 2025/05/26 19:00 테스트 메시지
팔로워랩 입금 2025/05/26 19:00 테스트 메시지
```

#### SMS 메시지
```
입금 관련 테스트 메시지
```

### 3. 로그 확인
- 시작 시 현재 모드 확인: `DepositCheckAPI 초기화 - 모드: 테스트/운영`
- API 호출 URL 확인: `API 호출 - URL: ...`

## 운영 배포

운영 환경 배포 시:
```bash
# 환경변수 제거 또는 false 설정
unset SLACK_BOT_TEST_MODE
# 또는
export SLACK_BOT_TEST_MODE=false

# 서버 재시작
python main.py
```

