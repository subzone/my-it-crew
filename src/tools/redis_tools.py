import redis
from src.config import redis_client

def get_redis_connection():
    return redis_client
