
import redis
from common import config

redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    password=config.REDIS_PASSWORD,
    db=config.REDIS_DB,
    decode_responses=True  # 문자열로 받으려면 True로 설정
)
