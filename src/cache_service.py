import redis
from typing import Optional


class CacheService:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.redis_client = redis.Redis(host=host, port=port, db=db)
        self.redis_client.ping()

    def get(self, key: str) -> Optional[str]:
        return self.redis_client.get(key)

    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        return self.redis_client.setex(key, ttl, value)

    def delete(self, key: str) -> int:
        return self.redis_client.delete(key)
