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

    # Sessão opaca (docs/adr/001-autenticacao-sessao-opaca-argon2.md).
    session_cookie_name: str = "vertere_session"
    session_cookie_secure: bool = True
    session_ttl_minutes: int = 30
    session_ttl_remember_me_days: int = 30
    session_renewal_threshold_minutes: int = 10

    # Consulta de CEP (autofill de endereço) — sem chave, mas configurável para
    # apontar a um stub em ambiente de teste sem tocar código.
    viacep_base_url: str = "https://viacep.com.br"
    viacep_timeout_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()  # database_url comes from the environment
