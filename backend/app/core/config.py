"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://aifc:aifc@localhost:5432/aifc"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_PATH: str = "./storage"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # App
    DEBUG: bool = True
    APP_NAME: str = "AI File Converter"
    API_V1_PREFIX: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
