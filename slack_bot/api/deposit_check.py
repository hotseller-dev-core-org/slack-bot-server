from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from http import HTTPStatus
from re import sub
from typing import Any, Dict, Final, List, Optional, Tuple, Union

import requests
from advertools import emoji

from common import aio_log_method_call, config, set_logger
from common.redis import redis_client
from slack_bot.slack import SlackAPI

# 채널 ID 상수
_HOT_AUTO_DEPOSIT_CHANNEL_ID: Final[str] = "C025V0PJZ1P"
_SNS_TOOL_DEPOSIT_CHANNEL_ID: Final[str] = "C08CHA1TZQW"
_MONEYCOON_DEPOSIT_CHANNEL_ID: Final[str] = "C0376RS8KLZ"
_JAPAN_NIHON_DEPOSIT_CHANNEL_ID: Final[str] = "C05LS9VF5DY"
_JAPAN_TOMO_DEPOSIT_CHANNEL_ID: Final[str] = "C06C3HG1Q0K"
_JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID: Final[str] = "C08F10YTBKK"
_SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID: Final[str] = "C08BR1P920H"
_SERVICE_TEAM_SMS_CHANNEL_ID: Final[str] = "C05NYEWHK1S"

# 에러 코드 상수
class ErrorCodes:
    DUPLICATE_DEPOSIT_PARTNER = ['300706', '300711']
    JAPAN_IGNORE_CODE = ['001006']

# 채널 그룹 정의
class ChannelGroups:
    JAPAN_CHANNELS = [
        _JAPAN_NIHON_DEPOSIT_CHANNEL_ID,
        _JAPAN_TOMO_DEPOSIT_CHANNEL_ID,
        _JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID,
    ]

    JAPAN_SMS_CHANNELS = [
        _JAPAN_NIHON_DEPOSIT_CHANNEL_ID,
        _JAPAN_TOMO_DEPOSIT_CHANNEL_ID,
        _JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID,
        _SERVICE_TEAM_SMS_CHANNEL_ID
    ]

# API URL 매핑
API_URL_MAPPING = {
    _HOT_AUTO_DEPOSIT_CHANNEL_ID: "http://10.0.23.222/api/point",
    _SNS_TOOL_DEPOSIT_CHANNEL_ID: "https://api.snstool.co.kr/api/point",
    # TODO: TEST
    _SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID: "http://api.hotpartners.co.kr/partner/point/auto-charge",
    # _SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID: "http://10.0.2.216/partner/point/auto-charge",
}

JAPAN_MAPPING_INFO: Dict[str, str] = {
    _JAPAN_NIHON_DEPOSIT_CHANNEL_ID: 'snsmart00@outlook.com',
    _JAPAN_TOMO_DEPOSIT_CHANNEL_ID: 'snstomo',
    _JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID: 'snstomo',
}

@dataclass
class ParseResult:
    data: Dict[str, Any]
    is_valid: bool = True

@dataclass
class ProcessingResult:
    emoji_name: Optional[str] = None
    message: Optional[str] = None

_PKG = 'deposit_check'
_LOGGER = set_logger(_PKG)

class DepositCheckAPI:
    TRIGGER_CHANNEL_ID = [
        _MONEYCOON_DEPOSIT_CHANNEL_ID,
        _HOT_AUTO_DEPOSIT_CHANNEL_ID,
        _SNS_TOOL_DEPOSIT_CHANNEL_ID,
        _JAPAN_NIHON_DEPOSIT_CHANNEL_ID,
        _JAPAN_TOMO_DEPOSIT_CHANNEL_ID,
        _JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID,
        _SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID,
        _SERVICE_TEAM_SMS_CHANNEL_ID
    ]
    TRIGGER_KEYWORD = ['*']

    USE_ACTION_FEATURE = False
    FOLLOW_CHANNEL_MESSAGE = True

    def __init__(self):
        self.logger = set_logger("api")
        self.slack_api = SlackAPI(config.SLACK_APP_TOKEN)

    async def processing(
        self,
        channel_id: str,
        thread_ts: str,
        txt_list: Union[str, List[str]],
        elements_list: List[Dict[str, Any]] = [],
        *args,
        **kwargs,
    ) -> None:
        """메인 처리 메서드"""
        # 중복 이벤트 체크
        if not self._check_duplicate_event(kwargs.get('event_id') or thread_ts):
            return

        _LOGGER.info(f"channel_id: {channel_id}, event_id: {kwargs.get('event_id')}")

        # 메시지 파싱
        parse_result = self._parse_message(channel_id, txt_list, elements_list)
        if not parse_result.is_valid:
            return

        # API 호출 및 응답 처리
        await self._process_api_call(channel_id, thread_ts, parse_result.data)

    def _check_duplicate_event(self, event_id: str) -> bool:
        """중복 이벤트 체크"""
        redis_key = f"slack_event:{event_id}"
        if redis_client.get(redis_key):
            self.logger.info(f"중복 이벤트 발생 (event_id: {event_id})")
            return False

        redis_client.setex(redis_key, 600, "1")
        return True

    def _parse_message(self, channel_id: str, txt_list: Union[str, List[str]], elements_list: List[Dict[str, Any]]) -> ParseResult:
        """메시지 파싱"""
        txt = txt_list if isinstance(txt_list, str) else ' '.join(txt_list)
        txt_content = txt.split()

        try:
            if channel_id in ChannelGroups.JAPAN_CHANNELS:
                return self._parse_japan_message(channel_id, txt, txt_content, elements_list)
            elif channel_id == _SERVICE_TEAM_SMS_CHANNEL_ID:
                return self._parse_sms_message(txt)
            else:
                return self._parse_standard_message(txt_content)
        except Exception as e:
            _LOGGER.exception(e)
            return ParseResult(data={}, is_valid=False)

    def _parse_japan_message(self, channel_id: str, txt: str, txt_content: List[str], elements_list: List[Dict[str, Any]]) -> ParseResult:
        """일본 채널 메시지 파싱"""
        # 일본 입금 내용 검증
        valid_prefixes = [
            ("니혼", "입금"), ("토모", "입금"), ("팔로워랩", "입금")
        ]

        is_valid = any(
            txt_content[0].startswith(prefix[0]) and txt_content[1].startswith(prefix[1])
            for prefix in valid_prefixes
        )

        if not is_valid:
            _LOGGER.info(f"일본 입금 내용이 아님 (txt_content: {txt_content})")
            return ParseResult(data={}, is_valid=False)

        # 날짜 파싱
        if "이메일" in txt_content[0].strip():
            order_date = f'{txt_content[1]} {txt_content[2]}'.replace('/', '-')
        else:
            order_date = f'{txt_content[0]} {txt_content[1]}'.replace('/', '-')

        # 이모지 처리
        new_txt = self._process_emoji_elements(txt, elements_list)

        return ParseResult(data={
            'date': order_date,
            'to': JAPAN_MAPPING_INFO[channel_id],
            'message': new_txt,
        })

    def _parse_sms_message(self, txt: str) -> ParseResult:
        """SMS 채널 메시지 파싱"""
        if "입금" not in txt:
            _LOGGER.info(f"'입금'이 포함 안됨.")
            return ParseResult(data={}, is_valid=False)

        return ParseResult(data={
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'to': "None",
            'message': txt,
        })

    def _parse_standard_message(self, txt_content: List[str]) -> ParseResult:
        """표준 메시지 파싱"""
        # HOT_PARTNERS 채널의 경우 7개 요소: ['2025/05/26', '18:20', '입금', '10,000원', '백다예', '029***4650451', '기업']
        # 기존 채널의 경우 5개 요소: ['2025/05/26', '18:20', '입금', '10,000원', '백다예']

        if len(txt_content) not in [5, 7]:
            _LOGGER.info(f"유효하지 않는 문자임 (5 또는 7개 요소 필요) (txt_content: {txt_content})")
            return ParseResult(data={}, is_valid=False)

        if txt_content[2] != "입금":
            _LOGGER.info(f"'입금'이 포함 안됨.(txt_content: {txt_content})")
            return ParseResult(data={}, is_valid=False)

        # 날짜와 시간 조합
        order_date = f'{txt_content[0]} {txt_content[1]}'.replace('/', '-')

        # 금액 처리 (쉼표와 '원' 제거)
        amount_str = txt_content[3]
        amount = Decimal(sub(r'[^\d.]', "", amount_str))  # 숫자와 점만 남김

        if not amount:
            _LOGGER.info(f"amount가 0임 (txt_content: {txt_content})")
            return ParseResult(data={}, is_valid=False)

        # 예금주명 처리 (띄어쓰기 포함하여 하나의 이름으로)
        deposit_acct_holder = txt_content[4]

        return ParseResult(data={
            'order_date': order_date,
            'amount': int(amount),
            'deposit_acct_holder': deposit_acct_holder,
        })

    def _process_emoji_elements(self, txt: str, elements_list: List[Dict[str, Any]]) -> str:
        """이모지 요소 처리"""
        if not elements_list:
            return txt

        new_txt = ''
        for element in elements_list:
            if element.get('type') == 'emoji':
                code = element.get('unicode', '').replace('-', ' ')
                res = emoji.emoji_search(code)

                if not len(res):
                    raise Exception(f"No emoji. {element}")

                emoji_result = res.get('emoji')
                if emoji_result and len(emoji_result) > 0:
                    new_txt += emoji_result[0]
            else:
                new_txt += element.get('text', '')

        return new_txt

    def _get_api_url(self, channel_id: str) -> str:
        """채널별 API URL 반환"""
        if channel_id in API_URL_MAPPING:
            return API_URL_MAPPING[channel_id]
        elif channel_id in ChannelGroups.JAPAN_SMS_CHANNELS:
            return "http://10.0.2.21/api/payment/deposit"
        else:
            raise Exception(f"Not supported channel_id. ({channel_id})")

    async def _process_api_call(self, channel_id: str, thread_ts: str, parse_res: Dict[str, Any]) -> None:
        """API 호출 및 응답 처리"""
        _LOGGER.info(f"parse_res: {parse_res}")

        api_url = ""
        try:
            api_url = self._get_api_url(channel_id)

            # HOT_AUTO 채널의 경우 thread_ts 추가
            if channel_id == _HOT_AUTO_DEPOSIT_CHANNEL_ID:
                parse_res['thread_ts'] = thread_ts
                _LOGGER.info(f"[그코용] parse_res: {parse_res}")

            _LOGGER.info(f"api_url: {api_url}")
            resp = requests.post(api_url, json=parse_res, verify=False)
            _LOGGER.info(f"resp: {resp} / resp.text: {resp.text}")

            result = self._handle_api_response(channel_id, resp)

        except Exception as e:
            result = ProcessingResult(
                emoji_name='x',
                message=f"실패\n - 사유: {e}"
            )

        # 결과 전송
        _LOGGER.info(f"외부 API({api_url}) 호출 결과: {result}")
        await self._send_processing_result(channel_id, thread_ts, result)

    def _handle_api_response(self, channel_id: str, resp: requests.Response) -> ProcessingResult:
        """API 응답 처리"""
        if resp.status_code == HTTPStatus.OK:
            return self._handle_success_response(channel_id, resp)
        elif resp.status_code == HTTPStatus.BAD_REQUEST:
            return self._handle_bad_request_response(channel_id, resp)
        else:
            resp.raise_for_status()
            return ProcessingResult(emoji_name='x', message="알 수 없는 오류가 발생했습니다.")

    def _handle_success_response(self, channel_id: str, resp: requests.Response) -> ProcessingResult:
        """성공 응답 처리"""
        resp_data = resp.json()

        if channel_id in [_HOT_AUTO_DEPOSIT_CHANNEL_ID, _SNS_TOOL_DEPOSIT_CHANNEL_ID]:
            return ProcessingResult(
                emoji_name='white_check_mark',
                message=(
                    "처리 성공\n"
                    f" - 사이트이름: {resp_data.get('site_name', 'Unknown')}\n"
                    f" - 사이트아이디: {resp_data.get('site_id', 'Unknown')}"
                    f"({resp_data.get('idx', 'Unknown')})"
                )
            )

        elif channel_id in ChannelGroups.JAPAN_SMS_CHANNELS:
            return self._handle_japan_sms_success(resp_data, resp)

        else:
            emoji_name = 'white_check_mark'
            if resp_data.get('data', {}).get('is_success_charge', "True") == 'False':
                emoji_name = 'x'

            return ProcessingResult(
                emoji_name=emoji_name,
                message=f"처리 성공\n - 사이트 정보: {resp_data.get('data', '')}"
            )

    def _handle_japan_sms_success(self, resp_data: Dict[str, Any], resp: requests.Response) -> ProcessingResult:
        """일본/SMS 채널 성공 응답 처리"""
        if resp_data.get('status') == 'success':
            if "'payment_log_idx': None" in str(resp_data):
                return ProcessingResult(
                    emoji_name='x',
                    message=f"처리 실패\n - 에러: {resp.text}. 내역이 저장되었습니다."
                )
            else:
                return ProcessingResult(
                    emoji_name='white_check_mark',
                    message=f"처리 성공\n - 사이트 정보: {resp_data}. 포인트가 충전되었습니다."
                )

        return ProcessingResult(emoji_name=None, message=None)

    def _handle_bad_request_response(self, channel_id: str, resp: requests.Response) -> ProcessingResult:
        """400 에러 응답 처리"""
        try:
            resp_data = resp.json()

            if channel_id in [_HOT_AUTO_DEPOSIT_CHANNEL_ID, _SNS_TOOL_DEPOSIT_CHANNEL_ID]:
                return ProcessingResult(
                    emoji_name='x',
                    message=f"처리 실패\n - 에러: {resp_data}"
                )

            elif channel_id in ChannelGroups.JAPAN_SMS_CHANNELS:
                return self._handle_japan_sms_error(resp_data, resp)

            else:
                return self._handle_partner_error(resp_data, resp)

        except Exception:
            resp.raise_for_status()
            return ProcessingResult(emoji_name='x', message="JSON 파싱 오류가 발생했습니다.")

    def _handle_japan_sms_error(self, resp_data: Dict[str, Any], resp: requests.Response) -> ProcessingResult:
        """일본/SMS 채널 에러 처리"""
        if str(resp_data.get('code')) not in ErrorCodes.JAPAN_IGNORE_CODE:
            return ProcessingResult(
                emoji_name='x',
                message=f"처리 실패\n - 에러: {resp.text}"
            )
        return ProcessingResult(emoji_name=None, message=None)

    def _handle_partner_error(self, resp_data: Dict[str, Any], resp: requests.Response) -> ProcessingResult:
        """파트너 채널 에러 처리"""
        # 중복 입금의 경우 이모지 없음
        if str(resp_data.get('code')) in ErrorCodes.DUPLICATE_DEPOSIT_PARTNER:
            emoji_name = None
        else:
            emoji_name = 'x'

        return ProcessingResult(
            emoji_name=emoji_name,
            message=(
                "처리 실패\n"
                f" - 에러: {resp}\n"
                f" - 사유: {resp_data.get('message', 'Unknown')} "
                f"({resp_data.get('code', 'Unknown')})"
            )
        )

    async def _send_processing_result(self, channel_id: str, thread_ts: str, result: ProcessingResult) -> None:
        """처리 결과 전송"""
        if result.emoji_name:
            self.slack_api.add_reaction(
                channel_id,
                thread_ts=thread_ts,
                emoji_name=result.emoji_name,
            )

        if result.message is not None:
            await self.send_result(
                channel_id,
                thread_ts=thread_ts,
                text=result.message
            )

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