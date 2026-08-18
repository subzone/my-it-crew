import pytest
from src.agents.base import SettingsConfigDict

def test_settings():
    settings = SettingsConfigDict()
    assert settings.VAULT_ADDR == "http://localhost:8200"
    assert settings.VAULT_TOKEN == "my_token"
