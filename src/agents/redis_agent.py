import redis

class RedisAgent:
    def __init__(self, host: str, port: int, db: int):
        self.host = host
        self.port = port
        self.db = db
        self.redis_client = redis.Redis(host=host, port=port, db=db)

    def get(self, key: str):
        return self.redis_client.get(key)

    def set(self, key: str, value: str):
        self.redis_client.set(key, value)
