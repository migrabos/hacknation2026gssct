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

    llm_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_s: float = 12.0
    ollama_max_tokens: int = 700
    ollama_temperature: float = 0.2

    adapter_timeout_s: float = 20.0

    # Whole /analyze target. The LLM only gets whatever time is left after the
    # data + engine steps; when too little is left, the template narrative is used.
    analyze_budget_s: float = 30.0
    data_budget_s: float = 25.0      # all data adapters together (plot + terrain + meteo + …)
    llm_min_time_s: float = 4.0      # less than this left → skip LLM, use template
    llm_retry_min_time_s: float = 10.0  # stricter retry only if at least this much is left


@lru_cache
def get_settings() -> Settings:
    return Settings()
