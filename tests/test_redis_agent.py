import pytest
from src.agents.redis_agent import RedisAgent

@pytest.fixture
def redis_agent():
    return RedisAgent(host='localhost', port=6379, password='password', database=0)

def test_redis_agent(redis_agent):
    assert redis_agent.ping() == b'PONG'