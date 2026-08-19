import pytest
from src.config import Settings

def test_config():
    settings = Settings()
    assert settings.redis_host == 'localhost'
    assert settings.redis_port == 6379
    assert settings.redis_db == 0
