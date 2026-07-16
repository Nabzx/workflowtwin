"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Validated runtime configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="WORKFLOWTWIN_",
        extra="ignore",
        frozen=True,
    )

    service_name: str = "workflowtwin-api"
    environment: Environment = "local"
    log_level: LogLevel = "INFO"
    database_url: str = Field(
        default="postgresql+asyncpg://workflowtwin:workflowtwin@localhost:5432/workflowtwin",
        description="SQLAlchemy async database URL.",
    )


@lru_cache
def get_settings() -> Settings:
    """Load and cache one settings object for the process lifetime."""
    return Settings()
