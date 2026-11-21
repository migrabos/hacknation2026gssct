"""Runtime configuration from environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    engine_version: str = "0.1.0"

    llm_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_s: float = 12.0
    ollama_max_tokens: int = 700
    ollama_temperature: float = 0.2

    adapter_timeout_s: float = 20.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
