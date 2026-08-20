import unittest
from src.config import redis_client

class TestRedisConfig(unittest.TestCase):
    def test_redis_connection(self):
        self.assertIsNotNone(redis_client)
