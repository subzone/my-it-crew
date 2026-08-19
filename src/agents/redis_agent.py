import redis

def connect_to_redis(host: str, port: int, password: str, db: int) -> redis.Redis:
    client = redis.Redis(host=host, port=port, password=password, db=db)
    return client