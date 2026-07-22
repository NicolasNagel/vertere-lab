"""Environment-driven settings.

DATABASE_URL is required: the app must fail fast and loudly when it is
missing, never fall back to an implicit database.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    # SecretStr: the URL carries credentials and must never reach a log.
    database_url: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()  # database_url comes from the environment
