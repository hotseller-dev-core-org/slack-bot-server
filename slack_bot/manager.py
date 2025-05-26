from copy import deepcopy
from typing import Any, Dict

from common.config import config
from common.logger import set_logger
from common.module import Singleton
from slack_bot.api import deposit_check
from slack_bot.slack import SlackAPI
from slack_bot.utils import parse_txt_from_blocks


class manager(metaclass=Singleton):
    def __init__(self):
        self._logger = set_logger("api")
        self._load_api_instance()

    def _load_api_instance(self):
        """
        api 하위에 존재하는 모듈 정보를 list 에 포함
        각 api 모듈의 이름과 class 는 아래와 같은 포맷으로 정의되어야함
            - 모듈 이름 예시: test.py
            - 모듈 내 class 정의 예시 : testAPI
        """
        self._apis = {}
        for dirstr in dir(deposit_check):
            if not dirstr.endswith("API"):
                continue

            api_name = dirstr[:-3].lower()
            if api_name in ['base']:  # 제외할 API 추가
                continue

            api_ins = getattr(deposit_check, dirstr)
            self._apis[api_name] = {
                'ins': api_ins,
                'trigger_channel_ids': getattr(
                    api_ins, 'TRIGGER_CHANNEL_ID', []
                ),
                'trigger_keywords': getattr(
                    api_ins, 'TRIGGER_KEYWORD', []
                ),
                'use_action_feature': getattr(
                    api_ins, 'USE_ACTION_FEATURE', False
                ),
                'follow_channel_message': getattr(
                    api_ins, 'FOLLOW_CHANNEL_MESSAGE', False
                )
            }

    async def _call_api(
        self,
        type: str,
        api_name: str,
        *args,
        **kwargs,
    ) -> Dict[str, Any] | None:
        if api_name not in self._apis:
            raise Exception(f"{api_name} API not found")  # api_name에 맞는 로드된 API가 없음

        # 호출된 api에 맞는 로직 수행
        # (호출시 마다 api module instance 생성)
        _mod = self._apis[api_name]['ins']()
        if not _mod:
            self._logger.error(f"{api_name} API module is None.")
            raise Exception(f"{api_name} API module is None")

        if type == 'event':
            resp = await _mod.processing(*args, **kwargs)
        elif type == 'action':
            resp = await _mod.processing_callback(*args, **kwargs)
        else:
            raise Exception(f"Unknown type: {type}")  # TODO

        return resp

class MentionEventManager(manager):
    def __init__(self):
        super(MentionEventManager, self).__init__()

    async def run(
        self,
        *args,
        **kwargs,
    ) -> Dict[str, Any] | None:
        conf = dict(kwargs)

        # 요청 데이터 복사 (해당 conf 값을 기준으로 계속 작업 진행)
        dup_conf = deepcopy(conf)

        if not dup_conf.get('event'):
            # 이벤트 정보가 없는 경우 로직 종료
            return None

        event = dup_conf['event']

        # 전달된 메세지와 채널에 대해 처리할 수 있는 API가 있는지 확인
        call_api_name = ''

        channel_id = event['channel']
        msg_list_only_txt = parse_txt_from_blocks(event['blocks'][0])
        if not msg_list_only_txt:
            _ = SlackAPI(config.SLACK_APP_TOKEN).send_post_message(
                channel_id=event['channel'],
                text="```사용 가능한 명령어는 아래와 같습니다.\n- '@봇쿤 입금확인': 입금 확인 요청을 처리합니다.\n```",
            )

        for _msg in msg_list_only_txt:
            msg = _msg.strip()
            for api_name, api_info in self._apis.items():
                # TODO. 중복 키워드/채널이 있는경우 우선순위를 부여하던가, 중복값이 세팅 안되게 해야함.
                # 각 API에 정의된 키워드와 채널 ID 값이 '*' 인경우, 검사하지 않고 스킵
                _keywords = api_info['trigger_keywords']
                if _keywords[0] != '*':
                    if msg not in _keywords:
                        continue

                _channel_ids = api_info['trigger_channel_ids']
                if _channel_ids[0] != '*':
                    if channel_id not in _channel_ids:
                        continue

                call_api_name = api_name
                break

        if not call_api_name:
            # 처리할 수 있는 API가 존재하지 않다면 종료
            return None

        try:
            call_kwargs = {
                'channel_id': channel_id,
            }
            resp_data = await self._call_api(
                'event',
                call_api_name,
                **call_kwargs,
            )
        except Exception as e:
            self._logger.error(f"Error in {call_api_name} API: {str(e)}")
            raise

        return resp_data


MENTION_EVENT_MANAGER = MentionEventManager()


class MsgEventManager(manager):
    def __init__(self):
        super(MsgEventManager, self).__init__()

    async def run(
        self,
        *args,
        **kwargs,
    ) -> Dict[str, Any] | None:
        conf = dict(kwargs)

        # 요청 데이터 복사 (해당 conf 값을 기준으로 계속 작업 진행)
        dup_conf = deepcopy(conf)

        if not dup_conf['event']:
            # 이벤트 정보가 없는 경우 로직 종료
            return None

        event = dup_conf['event']

        channel_id = event['channel']

        blocks = event.get('blocks')
        elements = None
        detail_elements = None

        if blocks:
            elements = blocks[0].get('elements')

            if elements:
                detail_elements = elements[0].get('elements')

        received_msg = event['text']
        if not received_msg:
            return None

        for api_name, api_info in self._apis.items():
            # 채널 메세지를 팔로우 하고 있는 API (FOLLOW_CHANNEL_MESSAGE = True) 만 처리
            if not api_info['follow_channel_message']:
                continue

            # 각 API에 정의된 키워드와 채널 ID 값이 '*' 인경우, 검사하지 않고 스킵
            _channel_ids = api_info['trigger_channel_ids']
            if _channel_ids[0] != '*':
                if channel_id not in _channel_ids:
                    continue

            try:
                call_kwargs = {
                    'channel_id': channel_id,
                    'thread_ts': event['ts'],
                    'txt_list': received_msg,
                    'elements_list': detail_elements,
                }
                if await self._call_api('event', api_name, **call_kwargs):
                    break

            except Exception as e:
                self._logger.error(f"Error in {api_name} API: {str(e)}")
                raise

        return None


MSG_EVENT_MANAGER = MsgEventManager()


class ActionManager(manager):
    def __init__(self):
        super(ActionManager, self).__init__()

    async def run(
        self,
        *args,
        **kwargs,
    ) -> Dict[str, Any] | None:
        conf = dict(kwargs)

        # 요청 데이터 복사 (해당 conf 값을 기준으로 계속 작업 진행)
        dup_conf = deepcopy(conf)

        if not dup_conf.get('action'):
            # 액션 정보가 없는 경우 로직 종료
            return None

        action = dup_conf['action']

        for api_name, api_info in self._apis.items():
            # 액션 기능을 처리하는 API (USE_ACTION_FEATURE = True) 만 처리
            if not api_info['use_action_feature']:
                continue

            try:
                call_kwargs = {
                    'channel_id': action['channel']['id'],
                    'thread_ts': action['message']['ts'],
                    'action_info': action['actions'][0],
                    'action_state': action['state']['values'],
                    'trigger_user': action['user']['username'],
                }
                if await self._call_api('action', api_name, **call_kwargs):
                    break

            except Exception as e:
                self._logger.error(f"Error in {api_name} API: {str(e)}")
                raise

        return None


ACTION_MANAGER = ActionManager()