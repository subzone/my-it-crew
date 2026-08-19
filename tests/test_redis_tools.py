import pytest
from src.tools.redis_tools import redis_client

def test_redis_connection():
    assert redis_client.ping() == True