import pytest
from src.agents.redis_agent import RedisAgent

class TestRedisAgent:
    def test_ping(self):
        agent = RedisAgent(host='localhost', port=6379, password='password', database=0)
        assert agent.ping()