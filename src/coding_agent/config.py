"""centralized configuration management using pydantic settings.

this module provides type-safe, validated configuration for the coding agent.
configuration is loaded from environment variables and optional .env files.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """main settings class for the coding agent.

    configuration is loaded from environment variables. a .env file in the
    working directory is also loaded if present.

    attributes:
        anthropic_api_key: api key for anthropic (claude)
        openai_api_key: api key for openai
        together_api_key: api key for together ai
        google_api_key: api key for google (gemini)
        tavily_api_key: api key for tavily web search
        llm_provider: explicit provider selection (auto-detected if not set)
        llm_model: model to use (provider default if not set)
        log_level: logging level (DEBUG, INFO, WARNING, ERROR)
        session_timeout: session timeout in seconds for api server
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore extra env vars
    )

    # api keys for llm providers
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    together_api_key: str | None = None
    google_api_key: str | None = None
    gemini_api_key: str | None = None  # alias for google

    # tool api keys
    tavily_api_key: str | None = None

    # llm configuration
    llm_provider: str | None = Field(default=None, alias="LLM_PROVIDER")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")

    # agent configuration
    log_level: str = Field(default="WARNING", alias="CODING_AGENT_LOG_LEVEL")
    session_timeout: int = Field(default=3600, ge=60)

    def get_google_api_key(self) -> str | None:
        """get google api key, checking both GOOGLE_API_KEY and GEMINI_API_KEY."""
        return self.google_api_key or self.gemini_api_key

    def detect_provider(self) -> str | None:
        """auto-detect provider based on available api keys.

        returns:
            provider name or None if no keys are set
        """
        if self.llm_provider:
            return self.llm_provider

        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        if self.together_api_key:
            return "together"
        if self.get_google_api_key():
            return "google"

        return None

    def get_api_key_for_provider(self, provider: str) -> str | None:
        """get the api key for a specific provider.

        args:
            provider: provider name (anthropic, openai, together, google)

        returns:
            api key or None if not set
        """
        key_map = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "together": self.together_api_key,
            "google": self.get_google_api_key(),
        }
        return key_map.get(provider)


@lru_cache
def get_settings() -> Settings:
    """get the singleton settings instance.

    uses lru_cache to ensure only one instance is created.
    call get_settings.cache_clear() to reload settings if needed.

    returns:
        the settings instance
    """
    return Settings()
