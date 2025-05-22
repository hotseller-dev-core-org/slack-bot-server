import json

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from common.logger import set_logger
from slack_bot.api.deposit_check import DepositCheckAPI

# from slack_bot.manager import ACTION_MANAGER, MENTION_EVENT_MANAGER, MSG_EVENT_MANAGER
from slack_bot.manager import ACTION_MANAGER

LOGGER = set_logger("slack_deposit_server.api")


router = APIRouter(prefix="/v1/slack", tags=["Slack"])
deposit_api = DepositCheckAPI()


@router.post("/event")
async def handle_event(request: Request):
    # try:
    #     body = await request.json()
    # except Exception as e:
    #     LOGGER.error(f"JSON decode error: {e}")
    #     return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    # """
    # e.g.
    # {
    #     'token': 'ap8mpFRNT9J0f67tFlLQVvXp', 'team_id': 'T022G500A2K', 'context_team_id': 'T022G500A2K',
    #     'context_enterprise_id': None, 'api_app_id': 'A08TF90UZ0C',
    #     'event': {
    #         'user': 'U065DG56882', 'type': 'message', 'ts': '1747827659.915939', 'client_msg_id': '013f4326-c7a3-46a6-8c7d-a03fd20934e6',
    #         'text': '2025/05/21 20:27\n입금 20,000원\n박다예\n029***46504051\n기업', 'team': 'T022G500A2K', 'blocks': [...], 'channel': 'C06MFPLN81W',
    #         'event_ts': '1747827659.915939', 'channel_type': 'group'
    #     },
    #     'type': 'event_callback', 'event_id': 'Ev08TFDA7AF6',
    #     'event_time': 1747827659, 'authorizations': [{...}], 'is_ext_shared_channel': False,
    #     'event_context': '4-eyJldCI6Im1lc3NhZ2UiLCJ0aWQiOiJUMDIyRzUwMEEySyIsImFpZCI6IkEwOFRGOTBVWjBDIiwiY2lkIjoiQzA2TUZQTE44MVcifQ'
    # }
    # """
    # LOGGER.info(f"Slack Event Body: {body}")

    # # Slack challenge 검증 처리
    # if "challenge" in body:
    #     return JSONResponse(content=body["challenge"])

    # event = body.get("event", {})
    # if not event:
    #     return Response(status_code=204)

    # # Ignore bot messages or message edits
    # if event.get("subtype") in ["bot_message", "message_changed"]:
    #     return Response(status_code=204)

    # channel_id = event.get("channel")
    # thread_ts = event.get("ts")
    # text = event.get("text", "")
    # event_id = body.get("event_id", thread_ts)

    # if "입금" not in text:
    #     LOGGER.info("입금 관련 메세지가 아님")
    #     return Response(status_code=204)

    # await deposit_api.processing(
    #     channel_id=channel_id,
    #     thread_ts=thread_ts,
    #     txt_list=text,
    #     elements_list=[],
    #     event_id=event_id,
    #     reaction_ts=event.get("ts") or thread_ts
    # )
    # # ===========

    # return JSONResponse(content={"ok": True}, status_code=200)
    raw_body = await request.body()
    try:
        # JSON 형식 처리 시도
        body = json.loads(raw_body)
    except Exception as e:
        # 만약 application/x-www-form-urlencoded 형태라면 수동 처리
        try:
            form = await request.form()
            payload = form.get("payload")
            if payload:
                # UploadFile일 경우 대비 → 내용을 읽고 디코딩
                if hasattr(payload, "read"):
                    payload_str = (await payload.read()).decode("utf-8")
                else:
                    payload_str = str(payload)

                body = json.loads(payload_str)

            else:
                raw_data = form.get("data", "{}")
                if hasattr(raw_data, "read"):
                    raw_data_str = (await raw_data.read()).decode("utf-8")
                else:
                    raw_data_str = str(raw_data)

                body = json.loads(raw_data_str)
        except Exception as e2:
            LOGGER.error(f"JSON decode error: {e}, fallback error: {e2}, raw_body: {raw_body}")
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    LOGGER.info(f"Slack Event Body: {body}")

    # ✅ Slack challenge 응답
    if "challenge" in body:
        return JSONResponse(content={"challenge": body["challenge"]})

    # ✅ 이벤트 처리
    event = body.get("event", {})
    if not event:
        return Response(status_code=204)

    if event.get("subtype") in ["bot_message", "message_changed"]:
        return Response(status_code=204)

    channel_id = event.get("channel")
    thread_ts = event.get("ts")
    text = event.get("text", "")
    event_id = body.get("event_id", thread_ts)

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