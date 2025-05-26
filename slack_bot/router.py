import json

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from common.logger import set_logger
from slack_bot.api.deposit_check import DepositCheckAPI

# from slack_bot.manager import ACTION_MANAGER, MENTION_EVENT_MANAGER, MSG_EVENT_MANAGER
from slack_bot.manager import ACTION_MANAGER

LOGGER = set_logger("api")


router = APIRouter(prefix="/v1/slack", tags=["Slack"])
deposit_api = DepositCheckAPI()

# Swagger 테스트용 모델 (Slack 이벤트 포맷에 맞춤)
class SlackEventModel(BaseModel):
    token: str
    team_id: str
    api_app_id: str
    event: dict
    type: str
    event_id: str | None = None
    challenge: str | None = None

@router.post("/event", response_model=dict)
async def handle_event(
    payload: SlackEventModel, request: Request
) -> Response:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        LOGGER.warning(f"Unsupported Content-Type: {content_type}")
        return JSONResponse(status_code=400, content={"error": "Only application/json is allowed"})

    body = payload.dict()
    LOGGER.info(f"Slack Event Body: {body}")

    # Slack challenge 응답
    if payload.challenge:
        return JSONResponse(content={"challenge": payload.challenge})

    # 이벤트 처리
    event = payload.event
    if not event:
        return Response(status_code=204)

    if event.get("subtype") in ["bot_message", "message_changed"]:
        return Response(status_code=204)

    # 봇이 보낸 메시지 필터링 (bot_id가 있는 경우)
    if event.get("bot_id"):
        LOGGER.info("봇 메시지이므로 처리하지 않음")
        return Response(status_code=204)

    channel_id = event.get("channel", "")
    thread_ts = event.get("ts", "")
    text = event.get("text", "")
    event_id = payload.event_id or thread_ts

    if "입금" not in text:
        LOGGER.info("입금 관련 메세지가 아님")
        return Response(status_code=204)

    await deposit_api.processing(
        channel_id=channel_id,
        thread_ts=thread_ts,
        txt_list=text,
        elements_list=[],
        event_id=event_id,
        reaction_ts=event.get("ts") or thread_ts
    )

    return JSONResponse(content={"ok": True}, status_code=200)


@router.post("/action")
async def handle_action(request: Request):
    """
    슬랙 블록 액션(버튼, 셀렉트 등) 처리 엔드포인트
    """
    try:
        req_form = await request.form()
        req_dict = req_form._dict
        req_payload_json = req_dict.get("payload")
        if not req_payload_json:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": "No payload"})

        # payload가 str이 아닐 경우 str로 변환
        if not isinstance(req_payload_json, str):
            req_payload_json = str(req_payload_json)
        action = json.loads(req_payload_json)

        await ACTION_MANAGER.run(action=action)
        return JSONResponse(content={"ok": True}, status_code=200)
    except Exception as e:
        LOGGER.error(f"Error in /action: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})