import json
from datetime import datetime
from typing import List
from common import config

import requests
from common.logger import set_logger

LOGGER = set_logger("slack_deposit_server.slack")


class SlackAPI(object):
    """ slacker 라이브러리 사용 불가 (2021.2.24 로 생성된 APP 에 한해서)
        (api.slack.com/changelog/2021-02-24-how-we-broke-your-slack-app)
        때문에 requests 방식으로 API 를 구현합니다.

    """
    def __init__(self, token: str) -> None:
        self._logger = set_logger("slack_deposit_server.slack")
        self.__token = token
        self._post_message_endpoint = "https://slack.com/api/chat.postMessage"
        self._add_reaction_endpoint = "https://slack.com/api/reactions.add"

    def _send_post_message(
        self,
        token:str,
        channel_id: str,
        thread_ts: str = "",
        text: str = "",
        attachments: List[dict] | None = None,
        blocks: List[dict] | None = None,
    ) -> object:
        req_data = {"channel": channel_id, "blocks": blocks}
        if thread_ts:
            req_data.update({"thread_ts": thread_ts})

        if text:
            req_data.update({"text": text})

        if attachments:
            req_data.update({"attachments": attachments})

        if blocks:
            req_data.update({"blocks": blocks})

        resp = requests.post(
            self._post_message_endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            data=json.dumps(req_data)
        )
        self._logger.info(f"Send post message result: {resp}, {resp.text}")
        return resp

    def send_post_message(
        self,
        channel_id: str,
        thread_ts: str = "",
        text: str = "",
        attachments: List[dict] | None = None,
        blocks: List[dict] | None = None,
    ) -> object:
        return self._send_post_message(
            self.__token, channel_id, thread_ts, text, attachments, blocks
        )

    def _add_reaction(
        self,
        token: str,
        channel_id: str,
        thread_ts: str,
        emoji_name: str,
    ) -> object:
        req_data = {
            "channel": channel_id,
            "timestamp": thread_ts,
            "name": emoji_name,
        }

        resp = requests.post(
            self._add_reaction_endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            data=json.dumps(req_data)
        )
        self._logger.info(f"Send add reaction result: {resp}, {resp.text}")
        return resp

    def add_reaction(
        self,
        channel_id: str,
        thread_ts: str,
        emoji_name: str,
    ) -> object:
        return self._add_reaction(
            self.__token, channel_id, thread_ts, emoji_name
        )


class SlackBlock(object):
    ACTION_ELEMENTS_MAX_CNT = 5
    CONTEXT_ELEMENTS_MAX_CNT = 10

    LABEL_TEXT_MAX_LEN = 2000

    # --------------- Blocks ---------------
    @staticmethod
    def actions(
        elements: List[dict],
        block_id: str = "",
    ) -> dict:
        if not elements:
            raise Exception("Elements are required.")

        if len(elements) > SlackBlock.ACTION_ELEMENTS_MAX_CNT:
            raise Exception(
                "Action maximum number of items is "
                f"{SlackBlock.ACTION_ELEMENTS_MAX_CNT}"
            )

        fmt =  {
            "type": "actions",
            "elements": elements
        }

        if block_id:
            fmt["block_id"] = block_id

        return fmt

    @staticmethod
    def context(
        elements,
        block_id = "",
    ):
        if not elements:
            raise Exception("Elements are required.")

        if len(elements) > SlackBlock.CONTEXT_ELEMENTS_MAX_CNT:
            raise Exception(
                "Context maximum number of items is "
                f"{SlackBlock.CONTEXT_ELEMENTS_MAX_CNT}"
            )

        fmt =  {
            "type": "actions",
            "elements": elements
        }

        if block_id:
            fmt["block_id"] = block_id

        return fmt

    @staticmethod
    def divider() -> dict:
        return {"type": "divider"}

    @staticmethod
    def file(
        external_id: str,
        source: str,
        block_id: str = "",
    ) -> dict:
        fmt =  {
            "type": "file",
            "external_id": external_id,
            "source": source,
        }

        if block_id:
            fmt["block_id"] = block_id

        return fmt

    @staticmethod
    def header(
        text: str,
        block_id: str = "",
    ) -> dict:
        fmt =  {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": text
            },
        }

        if block_id:
            fmt["block_id"] = block_id

        return fmt

    @staticmethod
    def section(
        text = {},  # text block
        fields = [],
        accessory = {},
        block_id = "",
    ):
        fmt =  {"type": "section"}
        if text:
            fmt["text"] = text

        if fields:
            fmt["fields"] = fields

        if accessory:
            fmt["accessory"] = accessory

        if block_id:
            fmt["block_id"] = block_id

        return fmt

    @staticmethod
    def input(
        label_text: str,
        elements: dict,
        block_id: str = "",
        use_emoji: bool = True
    ) -> dict:
        if len(label_text) > SlackBlock.LABEL_TEXT_MAX_LEN:
            raise Exception(
                "Maximum length for the text in this field is "
                f"{SlackBlock.LABEL_TEXT_MAX_LEN} characters."
            )

        fmt = {
            "type": "input",
            "label": {
                "type": "plain_text",
                "text": label_text,
                "emoji": use_emoji,
            },
            "element": elements,
        }

        if block_id:
            fmt["block_id"] = block_id

        return fmt

    # --------------- Block elements---------------
    @staticmethod
    def text_plain_text(text: str, use_emoji: bool = True) -> dict:
        fmt =  {
            "type": "plain_text",
            "text": f"{text}",
            "emoji": f"{use_emoji}",
        }
        return fmt

    @staticmethod
    def text_plain_text_input(
        action_id: str,
    ) -> dict:
        fmt =  {
            "type": "plain_text_input",
            "action_id": action_id,
        }
        return fmt

    @staticmethod
    def text_header(text: str, use_emoji: bool = True) -> dict:
        fmt =  {
            "type": "header",
            "text": f"{text}",
            "emoji": f"{use_emoji}",
        }
        return fmt

    @staticmethod
    def text_markdown(text: str) -> dict:
        fmt =  {
            "type": "mrkdwn",
            "text": f"{text}",
        }
        return fmt

    @staticmethod
    def button(
        btn_text: str,
        action_id: str,
        url: str = "",
        value: str = "",
        style: str = "",  # "primary" or "danger"
    ) -> dict:
        fmt =  {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": f"{btn_text}",
            },
            "action_id": action_id
        }

        if value:
            fmt["value"] = value

        if style:
            fmt["style"] = style

        if url:
            fmt["url"] = url

        return fmt

    @staticmethod
    def datepicker(
        text: str,
        action_id: str,
        initial_date: str = datetime.now().strftime("%Y-%m-%d"),
        use_emoji: bool = True,
    ) -> dict:
        fmt = {
            "type": "datepicker",
            "initial_date": initial_date,
            "placeholder": {
                "type": "plain_text",
                "text": text,
                "emoji": use_emoji,
            },
            "action_id": action_id,
        }

        return fmt

    @staticmethod
    def static_select(
        text: str,
        action_id: str,
        option_list: List[str],
        use_emoji: bool = True,
    ) -> dict:
        options = []
        for idx, op in enumerate(option_list):
            options.append({
                "text": {
                    "type": "plain_text",
                    "text": op,
                    "emoji": use_emoji,
                },
                "value": f"{op}-{idx}"
            })

        fmt = {
            "type": "static_select",
            "placeholder": {
                "type": "plain_text",
                "text": text,
                "emoji": use_emoji,
            },
            "options": options,
            "action_id": action_id,
        }

        return fmt


def main():
    token = config.SLACK_APP_TOKEN
    s = SlackAPI(token)
    s.send_post_message("C06MFPLN81W", "테스트", blocks=[SlackBlock.section(text="테스트")])


if __name__ == "__main__":
    main()
