from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Banco de dados ---
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/digest_db"

    # --- Claude API ---
    ANTHROPIC_API_KEY: str = ""
    AI_RELEVANCE_MODEL: str = "claude-haiku-4-5-20251001"
    AI_SUMMARY_MODEL: str = "claude-sonnet-4-6"
    AI_MIN_RELEVANCE_SCORE: int = 6
    AI_MAX_ARTICLES_PER_DIGEST: int = 10

    # --- Delivery RSS ---
    DELIVERY_WEBHOOK_URL: str = ""
    DELIVERY_RETRY_ATTEMPTS: int = 3

    # --- Scheduler RSS ---
    DIGEST_CRON_HOUR: int = 7
    DIGEST_CRON_TIMEZONE: str = "America/Sao_Paulo"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
