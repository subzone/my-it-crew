import redis

class RedisAgent:
    def __init__(self, host: str, port: int, password: str, db: int):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.client = redis.Redis(host=host, port=port, password=password, db=db)

    def ping(self) -> bool:
        return self.client.ping()