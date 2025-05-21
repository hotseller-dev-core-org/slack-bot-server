from app import create_app
from slack_bot.router import router as slack_router
from common.logger import set_logger

app = create_app()
# LOGGER = set_logger("slack_deposit_server.api")
LOGGER = set_logger("slack_deposit_server.api", json_format=True)

app.include_router(slack_router)

@app.get(
    "/ping",
    name="Health Check",
    tags=["헬스 체크"],
    description="API health-check 를 위한 Ping 테스트 API",
)
async def ping():
    LOGGER.info("info message~")
    LOGGER.debug("debug message~")
    LOGGER.warning("warning message~")
    LOGGER.error("error message~")
    LOGGER.info("info", extra={"status_code": 200, "error_message": "success"})
    LOGGER.debug("debug", extra={"status_code": 200, "error_message": "success"})
    LOGGER.warning("warning", extra={"status_code": 200, "error_message": "success"})
    LOGGER.error("error", extra={"status_code": 400, "error_message": "fail"})
    return "pong"
