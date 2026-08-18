import pytest
from src.config import SettingsConfigDict

@pytest.fixture
def settings():
    return SettingsConfigDict()

def test_redis_config(settings):
    assert settings.redis_host == "localhost"
    assert settings.redis_port == 6379
    assert settings.redis_password == os.getenv("REDIS_PASSWORD")
    assert settings.redis_database == 0
