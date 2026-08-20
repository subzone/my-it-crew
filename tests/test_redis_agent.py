import pytest
from src.agents.redis_agent import RedisAgent

class TestRedisAgent:
    @pytest.fixture
    def agent(self):
        return RedisAgent(host='localhost', port=6379, password=None, database=0)

    def test_ping(self, agent):
        assert agent.ping()