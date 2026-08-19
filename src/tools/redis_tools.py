import redis

class RedisTool:
    def __init__(self, host: str, port: int, db: int):
        self.host = host
        self.port = port
        self.db = db
        self.redis_client = redis.Redis(host=self.host, port=self.port, db=self.db)

    def ping(self) -> str:
        return self.redis_client.ping()
