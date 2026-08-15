"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings loaded from environment."""

    # LLM
    litellm_api_base: str = "http://litellm.ollama.svc:4000/v1"
    litellm_api_key: str = "sk-placeholder"

    # GitHub
    github_token: str = ""
    github_repo: str = "subzone/my-it-crew"

    # Agent defaults
    default_model: str = "qwen3.5-local"  # Local, free, 9B params
    reasoning_model: str = "nemotron-ultra"  # NVIDIA free tier, for heavy decisions
    fast_model: str = "nemotron-nano"  # NVIDIA free tier, for quick tasks

    # Scheduling
    cycle_interval_seconds: int = 300  # 5 minutes

    class Config:
        env_prefix = ""
        env_file = ".env"
