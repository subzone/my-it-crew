"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings loaded from environment."""

    # LLM — Primary (LiteLLM proxy routes all models)
    litellm_api_base: str = "http://litellm.ollama.svc:4000/v1"
    litellm_api_key: str = "sk-placeholder"

    # LLM — Model identifiers (routed via LiteLLM)
    # LiteLLM prefixes: openrouter/, sambanova/, ollama/ etc.
    default_model: str = "nemotron-nano"
    reasoning_model: str = "nemotron-ultra"
    fast_model: str = "nemotron-nano"

    # Agent-specific models (diverse LLMs = diverse code quality perspectives)
    model_nova: str = "nemotron-super"
    model_kai: str = "openrouter/qwen/qwen3-coder"
    model_zara: str = "sambanova/DeepSeek-R1"

    # GitHub
    github_token: str = ""
    github_repo: str = "subzone/my-it-crew"

    # Slack (legacy)
    slack_bot_token: str = ""

    # Mattermost
    mattermost_url: str = "http://mattermost.my-it-crew.svc:8065"
    mattermost_token: str = ""

    # Database
    database_url: str = "postgresql://cigance:c1g4nc3-s3cr3t-2024@cigance-db:5432/cigance"

    # Scheduling
    cycle_interval_seconds: int = 300  # 5 minutes

    class Config:
        env_prefix = ""
        env_file = ".env"
