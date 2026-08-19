import redis

class RedisAgent:
    def __init__(self, host: str, port: int, password: str, database: int):
        self.host = host
        self.port = port
        self.password = password
        self.database = database
        self.redis_client = None

    def connect(self) -> bool:
        try:
            self.redis_client = redis.Redis(host=self.host, port=self.port, password=self.password, db=self.database)
            return True
        except redis.exceptions.RedisError as e:
            print(f"Error connecting to Redis: {e}")
            return False

    def ping(self) -> str:
        try:
            return self.redis_client.ping()
        except redis.exceptions.RedisError as e:
            print(f"Error pinging Redis: {e}")
            return "Error"