import pytest
from src.agents.redis_agent import RedisAgent
from src.config import Settings

@pytest.fixture
def settings():
    return Settings(
        redis_host='localhost',
        redis_port=6379,
        redis_password='password',
        redis_db=0
    )

def test_redis_agent(settings):
    agent = RedisAgent(settings)
    assert agent.ping()