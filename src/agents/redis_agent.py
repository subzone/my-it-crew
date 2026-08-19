import redis

def connect_to_redis(host: str, port: int, password: str, db: int) -> redis.Redis:
    # Establish connection to Redis instance
    client = redis.Redis(host=host, port=port, password=password, db=db)
    return client

def health_check(client: redis.Redis) -> bool:
    # Health check endpoint (/redis/ping) returns PONG
    try:
        client.ping()
        return True
    except redis.exceptions.RedisError:
        return False