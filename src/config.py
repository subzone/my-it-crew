import os
from pydantic import BaseSettings

class SettingsConfigDict(BaseSettings):
    redis_host: str = 'localhost'
    redis_port: int = 6379
    redis_password: str = ''
    redis_database: int = 0