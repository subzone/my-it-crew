import redis

class RedisAgent:
    def __init__(self, host, port, password, database):
        self.host = host
        self.port = port
        self.password = password
        self.database = database
        self.redis_client = None

    def connect(self):
        self.redis_client = redis.Redis(host=self.host, port=self.port, password=self.password, db=self.database)

    def ping(self):
        return self.redis_client.ping()