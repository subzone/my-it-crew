import redis

class RedisTool:
    def __init__(self, host: str, port: int, db: int):
        self.redis_client = redis.Redis(host=host, port=port, db=db)

    def ping(self) -> str:
        return self.redis_client.ping()
