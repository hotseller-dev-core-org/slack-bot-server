# slack-deposit-server
slack-server에서 각 서비스별 슬랙 입금 알림방에 보내지는 deposit 내역을 처리하는 로직만 분리한 프로젝트



## 참고
- 이모지 붙이기
  - ✅ event["ts"] or event["event_ts"]
  - timestamp 파라미터로 전달
- 스레드 대댓글 달기
    - ✅ thread_ts = event["ts"]
    - 메시지의 루트에 달릴 댓글
- 슬랙 메시지 본문 확인
  - ✅ event["text"]
  - 입금 여부 확인
- 이벤트 추적
    - event_id
    - 로그 추적 용도, 메시지와는 무관
