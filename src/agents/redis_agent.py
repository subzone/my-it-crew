# Redis agent for IT ticket triage

class RedisAgent:
    def __init__(self, host: str, port: int, password: str, database: int):
        self.host = host
        self.port = port
        self.password = password
        self.database = database
        self.redis_client = None

    def connect(self):
        # Establish connection to Redis instance
        self.redis_client = redis.Redis(host=self.host, port=self.port, password=self.password, db=self.database)
        return self.redis_client

    def ping(self):
        # Health check endpoint
        if self.redis_client:
            return self.redis_client.ping()
        else:
            return None