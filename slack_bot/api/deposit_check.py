from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from re import sub
from typing import Any, Dict, Final, List, Union

import requests
from advertools import emoji

from common import config, set_logger
from common.redis import redis_client
from slack_bot.slack import SlackAPI

# 환경 설정 (환경변수로 제어 가능)
IS_TEST_MODE = config.SLACK_BOT_TEST_MODE
TEST_CHANNEL_ID = "C06MFPLN81W"  # 테스트용 통합 채널

# 채널 ID 설정
class ChannelConfig:
    @staticmethod
    def get_channel_id(prod_channel: str, test_channel: str = TEST_CHANNEL_ID) -> str:
        return test_channel if IS_TEST_MODE else prod_channel

# 채널 ID 상수
_HOT_AUTO_DEPOSIT_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C025V0PJZ1P")
_SNS_TOOL_DEPOSIT_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C08CHA1TZQW")
_MONEYCOON_DEPOSIT_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C0376RS8KLZ")
_JAPAN_NIHON_DEPOSIT_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C05LS9VF5DY")
_JAPAN_TOMO_DEPOSIT_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C06C3HG1Q0K")
_JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C08F10YTBKK")
_SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C08BR1P920H")
_SERVICE_TEAM_SMS_CHANNEL_ID: Final[str] = ChannelConfig.get_channel_id("C05NYEWHK1S")

# API URL 설정
class APIConfig:
    # 운영 환경 URL
    PROD_URLS = {
        'HOT_AUTO': "http://10.0.23.222/api/point",
        'SNS_TOOL': "https://api.snstool.co.kr/api/point",
        'HOT_PARTNERS': "http://10.0.2.216/partner/point/auto-charge",
        'SELF_MARKETING': "http://10.0.2.21/api/payment/deposit",
    }

    # 테스트 환경 URL
    TEST_URLS = {
        'HOT_AUTO': "https://api.growthcore.co.kr/api/point",
        'SNS_TOOL': "https://api.snstool.co.kr/api/point",
        'HOT_PARTNERS': "https://api.self-marketing-platform.co.kr/api/payment/deposit",
        'SELF_MARKETING': "https://api.self-marketing-platform.co.kr/api/payment/deposit",
    }

    @staticmethod
    def get_url(service_name: str) -> str:
        urls = APIConfig.TEST_URLS if IS_TEST_MODE else APIConfig.PROD_URLS
        return urls.get(service_name, "")

# 에러 코드 상수
class ErrorCodes:
    DUPLICATE_DEPOSIT_PARTNER = ['300706', '300711']
    SELF_MARKETING_IGNORE_CODE = ['001006']

# 채널 그룹 정의
class ChannelGroups:
    JAPAN_CHANNELS = [
        _JAPAN_NIHON_DEPOSIT_CHANNEL_ID,
        _JAPAN_TOMO_DEPOSIT_CHANNEL_ID,
        _JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID,
    ]

    SELF_MARKETING_CHANNELS = [
        _JAPAN_NIHON_DEPOSIT_CHANNEL_ID,
        _JAPAN_TOMO_DEPOSIT_CHANNEL_ID,
        _JAPAN_FOLLOWERLAB_DEPOSIT_CHANNEL_ID,
        _SERVICE_TEAM_SMS_CHANNEL_ID
    ]

# API URL 매핑
API_URL_MAPPING = {
    _HOT_AUTO_DEPOSIT_CHANNEL_ID: APIConfig.get_url('HOT_AUTO'),
    _SNS_TOOL_DEPOSIT_CHANNEL_ID: APIConfig.get_url('SNS_TOOL'),
    _SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID: APIConfig.get_url('HOT_PARTNERS'),
    _MONEYCOON_DEPOSIT_CHANNEL_ID: APIConfig.get_url('HOT_AUTO'),  # MONEYCOON도 HOT_AUTO와 동일한 URL 사용
}

# SELF_MARKETING 채널들 (HOT_PARTNERS 제외)
for channel_id in ChannelGroups.SELF_MARKETING_CHANNELS:
    API_URL_MAPPING[channel_id] = APIConfig.get_url('SELF_MARKETING')

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
    emoji_name: str | None = None
    message: str | None = None

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

        # 시작 시 현재 설정 로깅
        mode = "테스트" if IS_TEST_MODE else "운영"
        _LOGGER.info(f"DepositCheckAPI 초기화 - 모드: {mode}")
        if IS_TEST_MODE:
            _LOGGER.info(f"테스트 채널: {TEST_CHANNEL_ID}")

        # 채널 ID 상수값들 로깅
        _LOGGER.info("[INIT] 채널 ID 상수값들:")
        _LOGGER.info(f"[INIT] _HOT_AUTO_DEPOSIT_CHANNEL_ID: {_HOT_AUTO_DEPOSIT_CHANNEL_ID}")
        _LOGGER.info(f"[INIT] _SNS_TOOL_DEPOSIT_CHANNEL_ID: {_SNS_TOOL_DEPOSIT_CHANNEL_ID}")
        _LOGGER.info(f"[INIT] _SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID: {_SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID}")
        _LOGGER.info(f"[INIT] _SERVICE_TEAM_SMS_CHANNEL_ID: {_SERVICE_TEAM_SMS_CHANNEL_ID}")
        _LOGGER.info(f"[INIT] API_URL_MAPPING: {API_URL_MAPPING}")

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

        _LOGGER.info(f"[DEBUG] 메시지 파싱 시작 - channel_id: {channel_id}")
        _LOGGER.info(f"[DEBUG] 원본 텍스트: '{txt}'")
        _LOGGER.info(f"[DEBUG] 분할된 텍스트: {txt_content}")
        _LOGGER.info(f"[DEBUG] 요소 개수: {len(txt_content)}")

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
            _LOGGER.info("'입금'이 포함 안됨.")
            return ParseResult(data={}, is_valid=False)

        return ParseResult(data={
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'to': "None",
            'message': txt,
        })

    def _parse_standard_message(self, txt_content: List[str]) -> ParseResult:
        """표준 메시지 파싱"""
        # NOTE: 출금 메세지를 avoid 하기 위함
        if "입금" not in txt_content:
            _LOGGER.info(f"'입금'이 포함 안됨.(txt_content: {txt_content})")
            return ParseResult(data={}, is_valid=False)

        # 기존 로직과 동일: 정확히 5개 요소만 허용
        if len(txt_content) != 5:
            _LOGGER.info(f"유효하지 않는 문자임 (5개 요소 필요) (txt_content: {txt_content})")
            return ParseResult(data={}, is_valid=False)

        # 날짜와 시간 조합
        order_date = f'{txt_content[0]} {txt_content[1]}'.replace('/', '-')

        # 금액 처리 (쉼표와 '원' 제거) - 안전한 파싱
        try:
            amount_str = txt_content[3]
            _LOGGER.info(f"금액 파싱 시도: amount_str='{amount_str}'")

            # 숫자와 점만 남김
            cleaned_amount = sub(r'[^\d.]', "", amount_str)
            _LOGGER.info(f"정리된 금액: cleaned_amount='{cleaned_amount}'")

            if not cleaned_amount:
                _LOGGER.info(f"정리된 금액이 비어있음 (txt_content: {txt_content})")
                return ParseResult(data={}, is_valid=False)

            amount = Decimal(cleaned_amount)

        except (ValueError, Exception) as e:
            _LOGGER.error(f"금액 파싱 실패: {e}, amount_str='{txt_content[3] if len(txt_content) > 3 else 'N/A'}', txt_content: {txt_content}")
            return ParseResult(data={}, is_valid=False)

        if not amount:
            _LOGGER.info(f"amount가 0임 (txt_content: {txt_content})")
            return ParseResult(data={}, is_valid=False)

        # TODO: 확인 필요
        # 예금주명 처리 (띄어쓰기 포함하여 하나의 이름으로 처리할 필요 있음)
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
        """채널별 API URL 반환 (기존 로직과 동일)"""
        _LOGGER.info(f"[DEBUG] _get_api_url 호출 - channel_id: {channel_id}, IS_TEST_MODE: {IS_TEST_MODE}")
        _LOGGER.info(f"[DEBUG] _SERVICE_TEAM_SMS_CHANNEL_ID: {_SERVICE_TEAM_SMS_CHANNEL_ID}")
        _LOGGER.info(f"[DEBUG] channel_id == _SERVICE_TEAM_SMS_CHANNEL_ID: {channel_id == _SERVICE_TEAM_SMS_CHANNEL_ID}")
        _LOGGER.info(f"[DEBUG] channel_id in ChannelGroups.SELF_MARKETING_CHANNELS: {channel_id in ChannelGroups.SELF_MARKETING_CHANNELS}")

        # 기존 로직과 동일한 매핑
        if channel_id == _HOT_AUTO_DEPOSIT_CHANNEL_ID:
            return APIConfig.get_url('HOT_AUTO')
        elif channel_id == _SNS_TOOL_DEPOSIT_CHANNEL_ID:
            return APIConfig.get_url('SNS_TOOL')
        elif channel_id == _SERVICE_TEAM_HOT_PARTNERS_DEPOSIT_CHANNEL_ID:
            return APIConfig.get_url('HOT_PARTNERS')
        elif channel_id == _MONEYCOON_DEPOSIT_CHANNEL_ID:
            return APIConfig.get_url('HOT_AUTO')  # MONEYCOON은 HOT_AUTO와 동일한 URL
        elif channel_id in ChannelGroups.SELF_MARKETING_CHANNELS:
            return APIConfig.get_url('SELF_MARKETING')
        else:
            raise Exception(f"Not supported channel_id. ({channel_id})")

    async def _process_api_call(self, channel_id: str, thread_ts: str, parse_res: Dict[str, Any]) -> None:
        """API 호출 및 응답 처리"""
        api_url = ""
        try:
            api_url = self._get_api_url(channel_id)
            # TEST
            # api_url = "https://api.growthcore.co.kr/api/point"
            _LOGGER.info(f"호출 API URL: {api_url}")

            # HOT_AUTO 채널의 경우 thread_ts 추가
            if channel_id == _HOT_AUTO_DEPOSIT_CHANNEL_ID:
                parse_res['thread_ts'] = thread_ts

            # API 호출 시 헤더 설정
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            _LOGGER.info(f"[API 호출 정보]\nURL: {api_url}\nHeaders: {headers}\nData: {parse_res}")
            resp = requests.post(api_url, json=parse_res, headers=headers, verify=False)
            _LOGGER.info(f"[API 호출 결과]\nresp: {resp}\nresp.text: {resp.text}")

            result = self._handle_api_response(channel_id, resp)

        except Exception as e:
            result = ProcessingResult(
                emoji_name='x',
                message=f"실패\n - 사유: {e}"
            )

        # 결과 전송
        _LOGGER.info(f"[외부 API 호출 결과 처리 후]\nresult: {result}")
        await self._send_processing_result(channel_id, thread_ts, result)

    def _handle_api_response(self, channel_id: str, resp: requests.Response) -> ProcessingResult:
        """API 응답 처리"""
        if resp.status_code == HTTPStatus.OK:
            return self._handle_success_response(channel_id, resp)
        elif resp.status_code == HTTPStatus.BAD_REQUEST:
            return self._handle_bad_request_response(channel_id, resp)
        else:
            # 200이 아닌 모든 경우 실패 이모지
            return ProcessingResult(
                emoji_name='x',
                message=f"처리 실패\n - 상태코드: {resp.status_code}\n - 응답: {resp.text}"
            )

    def _handle_success_response(self, channel_id: str, resp: requests.Response) -> ProcessingResult:
        """성공 응답 처리 - 기존 로직 복원"""
        resp_data = resp.json()

        # HOT_AUTO, SNS_TOOL 채널
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

        # 셀프마케팅 플랫폼 채널들 (일본/SMS)
        elif channel_id in ChannelGroups.SELF_MARKETING_CHANNELS:
            if resp_data.get('status') == 'success':
                # payment_log_idx 체크로 실제 성공/실패 구분
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
            else:
                # status가 success가 아닌 경우 응답 없음
                return ProcessingResult(emoji_name=None, message=None)

        # HOT_PARTNERS 채널
        else:
            emoji_name = 'white_check_mark'
            # is_success_charge 필드 체크
            if resp_data.get('data', {}).get('is_success_charge', "True") == 'False':
                emoji_name = 'x'

            return ProcessingResult(
                emoji_name=emoji_name,
                message=f"처리 성공\n - 사이트 정보: {resp_data.get('data', '')}"
            )

    def _handle_bad_request_response(self, channel_id: str, resp: requests.Response) -> ProcessingResult:
        """400 에러 응답 처리"""
        try:
            resp_data = resp.json()

            # 중복 입금 에러 코드 체크 (파트너)
            if str(resp_data.get('code')) in ErrorCodes.DUPLICATE_DEPOSIT_PARTNER:
                return ProcessingResult(
                    emoji_name=None,  # 중복 입금은 이모지 없음
                    message=(
                        "처리 실패\n"
                        f" - 에러: {resp}\n"
                        f" - 사유: {resp_data.get('message', 'Unknown')} "
                        f"({resp_data.get('code', 'Unknown')})"
                    )
                )

            # 일본/SMS 무시할 에러 코드 체크
            elif (
                channel_id in ChannelGroups.SELF_MARKETING_CHANNELS and
                str(resp_data.get('code')) in ErrorCodes.SELF_MARKETING_IGNORE_CODE
            ):
                return ProcessingResult(emoji_name=None, message=None)

            # 그 외 모든 400 에러는 X 이모지
            else:
                return ProcessingResult(
                    emoji_name='x',
                    message=f"처리 실패\n - 에러: {resp_data}"
                )

        except Exception:
            # JSON 파싱 실패시에도 X 이모지
            return ProcessingResult(
                emoji_name='x',
                message=f"처리 실패\n - JSON 파싱 오류\n - 응답: {resp.text}"
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