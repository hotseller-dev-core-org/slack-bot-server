from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from re import sub

import requests
from advertools import emoji

from common import aio_log_method_call, config, set_logger
from common.redis import redis_client
from slack_bot.slack import SlackAPI


class DepositCheckAPI:
    def __init__(self):
        self.logger = set_logger("api")
        self.slack_api = SlackAPI(config.SLACK_APP_TOKEN)

    # @aio_log_method_call("slack_deposit_server.api")
    async def processing(
        self,
        channel_id: str,
        thread_ts: str,
        txt_list: str | list,
        elements_list: list = [],
        *args,
        **kwargs
    ) -> None:
        event_id = kwargs.get("event_id") or thread_ts
        reaction_ts = kwargs.get("reaction_ts") or thread_ts

        redis_key = f"slack_event:{event_id}"
        if redis_client.get(redis_key):
            # 중복이면 조용히 return (로깅 포함 전부 생략)
            return

        redis_client.setex(redis_key, 600, "1")

        txt_content = txt_list.split() if isinstance(txt_list, str) else txt_list

        try:
            parse_res = self._parse_message(channel_id, txt_content, elements_list)
        except Exception as e:
            self.logger.exception(e)
            await self.send_result(channel_id, thread_ts, str(e))
            return

        if not parse_res:
            return

        api_url = config.API_ENDPOINTS.get(channel_id)
        if not api_url:
            self.logger.error(f"Not supported channel_id. ({channel_id})")
            return

        if channel_id == config.CHANNEL_IDS["HOT_AUTO"]:
            parse_res["thread_ts"] = thread_ts

        await self._handle_api_response(api_url, channel_id, thread_ts, reaction_ts, parse_res)

    def _parse_message(self, channel_id: str, txt_content: list, elements: list) -> dict:
        if channel_id in config.JAPAN_CHANNELS:
            if not any(txt_content[0].startswith(x) and txt_content[1].startswith("입금") for x in ["니혼", "토모", "팔로워랩"]):
                self.logger.info(f"일본 입금 내용이 아님 (txt_content: {txt_content})")
                return {}

            order_date = (
                f"{txt_content[1]} {txt_content[2]}" if "이메일" in txt_content[0]
                else f"{txt_content[0]} {txt_content[1]}"
            ).replace("/", "-")

            message = self._parse_elements_to_text(txt_content, elements)
            return {
                "date": order_date,
                "to": config.JAPAN_MAPPING_INFO[channel_id],
                "message": message
            }

        elif channel_id == config.CHANNEL_IDS["SERVICE_TEAM_SMS"]:
            return {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "to": "None",
                "message": " ".join(txt_content)
            }

        else:
            if len(txt_content) != 5 or txt_content[2] != "입금":
                self.logger.info(f"유효하지 않거나 '입금' 없음 (txt_content: {txt_content})")
                return {}

            order_date = f"{txt_content[0]} {txt_content[1]}".replace("/", "-")
            amount = Decimal(sub(r"[^0-9.]", "", txt_content[3]))
            if not amount:
                self.logger.info(f"amount가 0임 (txt_content: {txt_content})")
                return {}

            return {
                "order_date": order_date,
                "amount": int(amount),
                "deposit_acct_holder": txt_content[4]
            }

    def _parse_elements_to_text(self, txt_list: str | list, elements: list) -> str:
        if not elements:
            return " ".join(txt_list) if isinstance(txt_list, list) else txt_list

        message = ""
        for element in elements:
            if element.get("type") == "emoji":
                code = element["unicode"].replace("-", " ")
                res = emoji.emoji_search(code)
                if res.get("emoji"):
                    message += res["emoji"][0]
            else:
                message += element.get("text", "")
        return message

    async def _handle_api_response(
        self,
        api_url: str,
        channel_id: str,
        thread_ts: str,
        reaction_ts: str,
        payload: dict
    ):
        emoji_name, resp_msg = "white_check_mark", None
        try:
            self.logger.info(f"api_url: {api_url}")
            resp = requests.post(api_url, json=payload, verify=False)
            self.logger.info(f"resp: {resp} / {resp.text}")

            if resp.status_code == HTTPStatus.OK:
                data = resp.json()
                if channel_id in config.JAPAN_CHANNELS:
                    if data.get("status") == "success":
                        if "'payment_log_idx': None" in str(data):
                            emoji_name, resp_msg = "x", f"저장 성공, 포인트 충전 실패\n{resp.text}"
                        else:
                            resp_msg = f"처리 성공\n{data}"
                    else:
                        emoji_name, resp_msg = None, None
                else:
                    resp_msg = f"처리 성공\n{data.get('data', '')}"
                    if data.get("data", {}).get("is_success_charge") == "False":
                        emoji_name = "x"

            elif resp.status_code == HTTPStatus.BAD_REQUEST:
                try:
                    data = resp.json()
                    emoji_name = "x"
                    if channel_id in config.JAPAN_CHANNELS and str(data.get("code")) not in ["001006"]:
                        resp_msg = f"실패\n{resp.text}"
                    elif channel_id == config.CHANNEL_IDS["HOT_AUTO"]:
                        resp_msg = f"실패\n{data}"
                    else:
                        resp_msg = f"실패\n{resp}\n사유: {data.get('message')} ({data.get('code')})"
                except Exception as e:
                    self.logger.exception(e)
                    resp.raise_for_status()
            else:
                resp.raise_for_status()

        except Exception as e:
            emoji_name, resp_msg = "x", f"실패\n사유: {e}"

        finally:
            if emoji_name:
                self.slack_api.add_reaction(channel_id, reaction_ts, emoji_name)
            if resp_msg:
                await self.send_result(channel_id, thread_ts, resp_msg)

    async def send_result(self, channel_id, thread_ts="", text="", attachments=None, blocks=None):
        resp = self.slack_api.send_post_message(
            channel_id, thread_ts=thread_ts, text=text,
            attachments=attachments, blocks=blocks
        )

        if isinstance(resp, requests.Response):
            self.logger.info(f"Send message to slack {channel_id} channel: {resp.status_code}")
        else:
            self.logger.warning(f"Slack response is not a Response object: {resp}")
        return True