import redis
from src.config import SettingsConfigDict

settings = SettingsConfigDict()
redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, password=settings.redis_password, db=settings.redis_database)