"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Borsel Handler application.

    All values are read from environment variables (or a .env file).
    """

    # Application
    APP_NAME: str = "Borsel Handler"
    DEBUG: bool = False

    # PostgreSQL / TimescaleDB
    DATABASE_URL: str = "postgresql+asyncpg://borsel:changeme@db:5432/borsel"

    # Redis (Celery broker)
    REDIS_URL: str = "redis://redis:6379/0"

    # Storage paths
    STORAGE_RAW_DIR: str = "storage/raw"
    STORAGE_EXTRACTED_DIR: str = "storage/extracted"
    STORAGE_PROCESSED_DIR: str = "storage/processed"
    STORAGE_QUARANTINE_DIR: str = "storage/quarantine"
    LOG_DIR: str = "storage/logs"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
