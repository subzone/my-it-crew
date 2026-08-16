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

    # Slack (legacy)
    slack_bot_token: str = ""

    # Mattermost
    mattermost_url: str = "http://mattermost.my-it-crew.svc:8065"
    mattermost_token: str = ""

    # Agent defaults
    default_model: str = "nemotron-nano"
    reasoning_model: str = "nemotron-ultra"
    fast_model: str = "nemotron-nano"

    # Scheduling
    cycle_interval_seconds: int = 300  # 5 minutes

    class Config:
        env_prefix = ""
        env_file = ".env"
