import pytest
from src.config import SettingsConfigDict

def test_settings():
    settings = SettingsConfigDict()
    assert settings.redis_host == 'localhost'