"""Runtime configuration from environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    engine_version: str = "0.2.0"

    # Comma-separated list of allowed browser origins ("*" = any)
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    adapter_timeout_s: float = 20.0

    # All data adapters share one deadline (plot + terrain + meteo + …).
    data_budget_s: float = 25.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
