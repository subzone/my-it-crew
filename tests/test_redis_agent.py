import unittest
from src.agents.redis_agent import connect_to_redis, ping_redis

class TestRedisAgent(unittest.TestCase):
    def test_connect_to_redis(self):
        client = connect_to_redis(host='localhost', port=6379, password=None, db=0)
        self.assertIsNotNone(client)
    def test_ping_redis(self):
        client = connect_to_redis(host='localhost', port=6379, password=None, db=0)
        self.assertTrue(ping_redis(client))
