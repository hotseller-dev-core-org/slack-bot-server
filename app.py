from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Slack Bot Server",
        description="슬랙 봇 서버",
        version="1.0.0"
    )

    # 라우터 등록은 main.py에서
    return app