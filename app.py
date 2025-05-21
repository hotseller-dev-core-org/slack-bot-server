from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(
        title="Slack Deposit Server",
        description="슬랙 입금 알림 자동화 서버",
        version="1.0.0"
    )

    # 라우터 등록은 main.py에서
    return app