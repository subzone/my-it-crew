import pytest
from src.tools.redis_tools import redis_client

@pytest.fixture
def redis_client_fixture():
    return redis_client

def test_redis_connection(redis_client_fixture):
    assert redis_client_fixture.ping() == True