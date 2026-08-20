import pytest
from src.tools.redis_tools import redis_client

@pytest.fixture
def redis():
    return redis_client