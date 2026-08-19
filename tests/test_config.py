import pytest
from src.config import redis_client

def test_redis_connection():
    assert redis_client.ping() == True