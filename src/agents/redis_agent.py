import redis
from src.config import Settings

class RedisAgent:
    def __init__(self, host: str, port: int, password: str, database: int):
        self.host = host
        self.port = port
        self.password = password
        self.database = database
        self.client = redis.Redis(host=host, port=port, password=password, db=database)

    def ping(self) -> bool:
        try:
            self.client.ping()
            return True
        except redis.exceptions.RedisError:
            return False
