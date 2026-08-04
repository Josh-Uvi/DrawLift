"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://aifc:aifc@localhost:5432/aifc"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_PATH: str = "./storage"
    STORAGE_TTL_DAYS: int = 7

    # ML models
    MODELS_PATH: str = "./models"
    SEGMENTER_MODEL_PATH: str | None = None
    SEGMENTER_MODEL_URL: str | None = None
    SEGMENTER_MODEL_INPUT_SIZE: int = 128

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # App
    DEBUG: bool = True
    APP_NAME: str = "AI File Converter"
    API_V1_PREFIX: str = "/api/v1"

    # DWG conversion
    DWG_CONVERTER_COMMAND: str | None = None

    # Job recovery
    # Seconds a job may remain in "processing" before being marked stale/failed.
    JOB_STALE_TIMEOUT_SECONDS: int = 300


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
