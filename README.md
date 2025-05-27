# Slack Bot Server

Slack 채널의 입금 메시지를 자동 파싱하여 외부 API로 전송하고, 결과에 따라 이모지 반응과 응답 메시지를 결과를 시각적으로 FastAPI 기반 서버입니다. 중복 이벤트 처리 방지를 위해 Redis를 사용합니다.

---

## 🧩 주요 기능

- **Slack 메시지 수신**: `/v1/slack/event` 엔드포인트로 입금 메시지 처리
- **자동 메시지 파싱**: 채널별 맞춤 파싱 (e.g. 일본, SMS, etc.)
- **외부 API 연동**: 파싱된 입금 문자메세지를 통해 얻은 데이터를 활용, 각 서비스별 API 호출 (e.g. 입금 내역 저장 API)
- **결과 피드백**: 성공/실패에 따른 이모지(✅/❌) 및 응답 메시지 자동 전송
- **중복 방지**: Redis 기반 이벤트 중복 처리 방지
- **환경별 설정**: 테스트/운영 환경 쉬운 전환

---

## 🗂️ 디렉토리 구조

```
.
├── main.py                       # FastAPI 앱 진입점
├── slack_bot/
│   ├── api/
│   │   ├── deposit_check.py      # 메시지 파싱 및 처리 로직 (메인)
│   │   └── router.py
│   ├── manager.py
│   ├── slack.py
│   └── utils.py                  # 유틸 함수
├── common/
│   ├── config.py                 # 설정 및 환경변수 관리
│   ├── logger.py                 # 로깅 설정
│   └── redis.py                  # Redis 클라이언트
├── requirements.txt
└── README.md
```

---

## ⚙️ 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 서버 실행
```bash
cd /home/ubuntu/src/slack-bot-server
./script/run.sh
```

---

## 🌍 환경별 설정

### 테스트 모드 활성화
- 환경 변수에서 제어
```bash
# 테스트 모드
SLACK_BOT_TEST_MODE=true

# 운영 모드
SLACK_BOT_TEST_MODE=false
```

### 채널 및 API 설정

#### 🧪 테스트 모드
- **모든 채널**: `C06MFPLN81W` (통합 테스트 채널)
- **API URLs**:
  - HOT_AUTO: `https://api.growthcore.co.kr/api/point`
  - SNS_TOOL: `https://api.snstool.co.kr/api/point`
  - HOT_PARTNERS: `https://api.self-marketing-platform.co.kr/api/payment/deposit`
  - SELF_MARKETING: `https://api.self-marketing-platform.co.kr/api/payment/deposit`

#### 🚀 운영 모드
- **채널별 설정**:
  - HOT_AUTO (그로스코어): `C025V0PJZ1P`
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
  - HOT_PARTNERS: `http://10.0.2.216/partner/point/auto-charge`
  - SELF_MARKETING: `http://10.0.2.21/api/payment/deposit`

---


## 🎯 응답 처리 로직

### ✅ 성공 이모지 (`white_check_mark`)
- **200 OK** 응답 + 비즈니스 로직 성공
- HOT_AUTO/SNS_TOOL: 사이트 정보 표시
- 셀프마케팅 플랫폼: `payment_log_idx` 존재 시
- HOT_PARTNERS: `is_success_charge: true` 시

### ❌ 실패 이모지 (`x`)
- **400 Bad Request** 중 일반 에러
- **기타**
- 셀프마케팅 플랫폼: `payment_log_idx: null` (저장만 성공)
- HOT_PARTNERS: `is_success_charge: false`

### 🚫 이모지 없음 (`None`)
- **중복 입금** (`300706`, `300711`)
- **무시할 에러** (`001006`)
- 셀프마케팅 플랫폼: `status != 'success'`

---

## 🔄 기존 로직과의 차이점

### ✨ 개선된 부분
#### 1. **테스트 | 운영 모드 스위칭 가능**
```
class APIConfig:
  PROD_URLS = {...}
  TEST_URLS = {...}
```
#### 2. **코드 구조화**
```python
# 기존: 200줄 넘는 하나의 메서드
async def processing(self, ...):
    # 모든 로직이 하나의 메서드에

# 현재: 기능별 메서드 분리
def _parse_message(self, ...):
def _parse_japan_message(self, ...):
def _handle_success_response(self, ...):
```
#### 3. **중복 이벤트 처리**
```python
# 기존: 메모리 기반 (서버 재시작 시 초기화)
self._processed_event_ids = OrderedDict()

# 현재: Redis 기반 이벤트 id 저장 (TTL 600초 -> 10분)
redis_key = f"slack_event:{event_id}"
```

#### 4. **명확한 네이밍**
```python
# 기존:
JAPAN_SMS_CHANNELS = [...]

# 현재: 일본 + SMS 포함 -> 명확한 네이밍
SELF_MARKETING_CHANNELS = [...]  # 일본 + SMS 포함
```

#### 5. **유연한 검증**
```python
# 기존: 엄격한 검증
if txt_content[2] != "입금":
    return

# 현재: 유연한 검증
if "입금" not in txt_content:
    return
```

### 🔄 동일하게 유지된 부분

- ✅ **비즈니스 로직**: 성공/실패 판단 기준 동일
- ✅ **메시지 파싱**: 채널별 파싱 규칙 동일
- ✅ **API 호출**: 데이터 형식 및 호출 방식 동일
- ✅ **응답 처리**: 이모지 및 메시지 규칙 동일
- ✅ **에러 처리**: 중복 입금, 무시할 에러 코드 동일

---

## 🧪 로그 확인
```bash
cd /var/log/slack-bot-server
tail -f _____.log
```

---

## 📡 API Endpoints

| 메서드 | URL                  | 설명                     |
|--------|----------------------|--------------------------|
| POST   | `/v1/slack/event`    | Slack Event 수신 처리     |
| POST   | `/v1/slack/action`   | Slack Block Action 처리   |

---

## 👨‍💻 개발자 참고

### 로깅
- `common/logger.py`를 통한 구조화된 로깅
- 채널별 디렉토리 구조로 로그 파일 생성
- 중복 출력 방지 및 파일 기반 로깅

### 확장성
- 새로운 채널 추가: `ChannelGroups`에 추가
- 새로운 API 연동: `APIConfig`에 URL 추가
- 새로운 파싱 규칙: `_parse_*_message` 메서드 추가

### 모니터링
- Redis 기반 중복 이벤트 추적
- 상세한 API 호출 로그
- 에러 발생 시 자동 알림 (Slack 메시지)

---
