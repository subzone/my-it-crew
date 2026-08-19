import pytest
from src.tools.redis_tools import redis_client

@pytest.fixture
def redis_client_fixture():
    return redis_client