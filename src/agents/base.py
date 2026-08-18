import os
from pydantic import BaseSettings

class SettingsConfigDict(BaseSettings):
    class Config:
        env_file = ".env"

    VAULT_ADDR: str = "http://localhost:8200"
    VAULT_TOKEN: str = "my_token"
