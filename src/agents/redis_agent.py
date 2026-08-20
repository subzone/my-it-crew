import redis

def connect_to_redis(host: str, port: int, password: str, database: int) -> redis.Redis:
    # Establish connection to Redis instance
    client = redis.Redis(host=host, port=port, password=password, db=database)
    return client

def health_check(client: redis.Redis) -> bool:
    # Health check endpoint (/redis/ping) returns PONG
    try:
        client.ping()
        return True
    except redis.exceptions.RedisError:
        return False