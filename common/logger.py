import logging
import os
import sys
import time
from functools import wraps

from traceloggerx.logutils.logger import set_logger as _set_logger

from common.config import config

ROOT_PKG = "slack_deposit_server"
DEFAULT_LOGGING_PATH = config.DEFAULT_LOGGING_PATH

def resolve_log_level(level=None):
    """문자열 로그 레벨을 logging 모듈 숫자 레벨로 변환"""
    if level is None:
        return logging.DEBUG
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.DEBUG)
    elif isinstance(level, int):
        return level

# 실제 logger 생성 함수
# pkg: logger 이름, log_dir: 로그 파일 경로, level: 로그 레벨 등
# 필요시 인자 추가 가능

def set_logger(pkg=None, log_dir=None, level=None, stream_only=False, json_format=False, extra=None):
    # pkg에서 점을 슬래시로 변경하여 디렉토리 구조 생성
    if pkg and '.' in pkg:
        # slack_deposit_server.api -> slack_deposit_server/api
        pkg_path = pkg.replace('.', '/')
        # 로그 디렉토리 경로 생성
        log_dir_path = os.path.join(log_dir or DEFAULT_LOGGING_PATH, os.path.dirname(pkg_path))
        os.makedirs(log_dir_path, exist_ok=True)
        # 파일명은 마지막 부분만 사용
        pkg_name = os.path.basename(pkg_path)
    else:
        pkg_name = pkg or ROOT_PKG
        log_dir_path = log_dir or DEFAULT_LOGGING_PATH

    return _set_logger(
        pkg=pkg_name,
        log_dir=log_dir_path,
        level=resolve_log_level(level),
        stream_only=stream_only,
        json_format=json_format,
        extra=extra
    )

def handle_exception(exc_type, exc_value, exc_traceback):
    """예외 발생 시 에러 로거를 통해 기록"""
    logger = _set_logger(f"{ROOT_PKG}.error", log_dir=DEFAULT_LOGGING_PATH)
    logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

def init_logger():
    """전역 예외 핸들러 설정 및 기본 로거 등록"""
    sys.excepthook = handle_exception
    _set_logger(ROOT_PKG, log_dir=DEFAULT_LOGGING_PATH)
    _set_logger(f"{ROOT_PKG}.error", log_dir=DEFAULT_LOGGING_PATH)

# 동기 함수용 로깅 데코레이터
def log_method_call(pkg):
    def decor(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            logger = _set_logger(pkg or ROOT_PKG, log_dir=DEFAULT_LOGGING_PATH)
            start = time.time()
            logger.debug(f"Start '{f.__name__}' args={args}, kwargs={kwargs}")
            result = f(*args, **kwargs)
            duration = time.time() - start
            logger.debug(f"End '{f.__name__}' duration={duration:.4f}s")
            return result
        return wrapper
    return decor

# 비동기 함수용 로깅 데코레이터
def aio_log_method_call(pkg):
    def decor(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            logger = _set_logger(pkg or ROOT_PKG, log_dir=DEFAULT_LOGGING_PATH)
            start = time.time()
            logger.debug(f"Start '{f.__name__}' args={args}, kwargs={kwargs}")
            result = await f(*args, **kwargs)
            duration = time.time() - start
            logger.debug(f"End '{f.__name__}' duration={duration:.4f}s")
            return result
        return wrapper
    return decor

# 즉시 초기화
init_logger()
