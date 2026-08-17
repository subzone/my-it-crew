"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings loaded from environment."""

    # LLM — Primary (LiteLLM proxy routes all models)
    litellm_api_base: str = "http://litellm.ollama.svc:4000/v1"
    litellm_api_key: str = "sk-placeholder"
    litellm_master_key: str = ""

    # LLM — Provider API keys (used by LiteLLM proxy, not directly by agents)
    openrouter_api_key: str = ""
    sambanova_api_key: str = ""
    groq_api_key: str = ""

    # LLM — Model identifiers (routed via LiteLLM)
    # LiteLLM prefixes: openrouter/, sambanova/, groq/, ollama/ etc.
    default_model: str = "nemotron-nano"
    reasoning_model: str = "nemotron-ultra"
    fast_model: str = "nemotron-nano"

    # Agent-specific models (diverse LLMs = diverse code quality perspectives)
    model_nova: str = "nemotron-super"
    model_kai: str = "groq/llama-3.3-70b-versatile"
    model_zara: str = "llama-3.3-70b"

    # GitHub
    github_token: str = ""
    github_repo: str = "subzone/my-it-crew"

    # Slack (legacy)
    slack_bot_token: str = ""

    # Mattermost
    mattermost_url: str = "http://mattermost.my-it-crew.svc:8065"
    mattermost_token: str = ""
    mattermost_token_nova: str = ""
    mattermost_token_kai: str = ""
    mattermost_token_zara: str = ""

    # Database
    database_url: str = "postgresql://cigance:c1g4nc3-s3cr3t-2024@cigance-db:5432/cigance"

    # Scheduling
    cycle_interval_seconds: int = 300  # 5 minutes

    class Config:
        env_prefix = ""
        env_file = ".env"
