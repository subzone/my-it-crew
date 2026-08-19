import redis

class RedisAgent:
    def __init__(self, host: str, port: int, password: str, database: int):
        self.host = host
        self.port = port
        self.password = password
        self.database = database
        self.client = None

    def connect(self) -> bool:
        try:
            self.client = redis.Redis(host=self.host, port=self.port, password=self.password, db=self.database)
            return True
        except redis.exceptions.ConnectionError:
            return False

    def ping(self) -> str:
        if self.client:
            return self.client.ping()
        else:
            return "Connection not established"