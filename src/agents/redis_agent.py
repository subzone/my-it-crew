import redis

class RedisAgent:
    def __init__(self, host: str, port: int, password: str, database: int):
        self.host = host
        self.port = port
        self.password = password
        self.database = database
        self.redis_client = None

    def connect(self) -> None:
        self.redis_client = redis.Redis(host=self.host, port=self.port, password=self.password, db=self.database)

    def health_check(self) -> bool:
        try:
            self.redis_client.ping()
            return True
        except redis.exceptions.RedisError:
            return False