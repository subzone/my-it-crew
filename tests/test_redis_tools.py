import pytest
from src.tools.redis_tools import ping_redis

@pytest.mark.asyncio
async def test_ping_redis() -> None:
    assert ping_redis() == True