import pytest
from src.tools.redis_tools import RedisTool

@pytest.fixture
def redis_tool():
    return RedisTool(host='localhost', port=6379, db=0)

def test_redis_ping(redis_tool):
    assert redis_tool.ping() == b'PONG'
