import pytest
import redis

def test_redis_connection():
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    assert redis_client.ping() == True
