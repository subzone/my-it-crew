import unittest
from src.agents.redis_agent import RedisAgent

class TestRedisAgent(unittest.TestCase):
    def test_ping(self):
        agent = RedisAgent(host='localhost', port=6379, password='', database=0)
        self.assertTrue(agent.ping())