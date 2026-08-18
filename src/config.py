from pydantic import BaseSettings

class SettingsConfigDict(BaseSettings):
    class Config:
        env_file = ".env"

    default_model: str = "text-davinci-002"
    litellm_api_base: str = "https://api.litellm.io/"
    litellm_api_key: str = "YOUR_API_KEY_HERE"
