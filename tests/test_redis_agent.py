import pytest
from src.agents.redis_agent import RedisAgent

@pytest.fixture
def redis_agent():
    return RedisAgent(host='localhost', port=6379, password=None, database=0)

def test_ping(redis_agent):
    assert redis_agent.ping() == True