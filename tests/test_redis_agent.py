import pytest
from src.agents.redis_agent import RedisAgent

@pytest.fixture
def redis_agent():
    return RedisAgent(host='localhost', port=6379, password='', database=0)

def test_redis_connection(redis_agent):
    redis_agent.connect()
    assert redis_agent.health_check()