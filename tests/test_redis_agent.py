# Unit tests for Redis agent

import unittest
from src.agents.redis_agent import RedisAgent


class TestRedisAgent(unittest.TestCase):
    def setUp(self):
        self.agent = RedisAgent(host='localhost', port=6379, password='', database=0)

    def test_connect(self):
        self.agent.connect()
        self.assertIsNotNone(self.agent.redis_client)

    def test_ping(self):
        self.agent.connect()
        self.assertEqual(self.agent.ping(), b'PONG')