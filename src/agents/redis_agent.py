import redis
from src.config import Settings

class RedisAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, password=settings.redis_password, db=settings.redis_db)
    
    def ping(self) -> bool:
        try:
            return self.redis_client.ping()
        except redis.exceptions.RedisError as e:
            print(f"Error pinging Redis: {e}")
            return False
