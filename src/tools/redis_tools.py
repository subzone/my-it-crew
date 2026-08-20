import redis
from src.config import Settings

settings = Settings()
redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, password=settings.redis_password, db=settings.redis_db)

def ping_redis() -> bool:
    try:
        redis_client.ping()
        return True
    except redis.exceptions.RedisError:
        return False