"""Environment-driven settings.

DATABASE_URL is required: the app must fail fast and loudly when it is
missing, never fall back to an implicit database.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
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
    # Default only covers local dev. **Production must set
    # TRUSTED_BROWSER_ORIGINS to the real frontend domain(s)** (JSON array,
    # e.g. '["https://app.vertere.com.br"]") — `api/middleware.py`'s
    # Origin-based CSRF guard rejects every authenticated mutation with 403
    # CSRF_ORIGIN_FORBIDDEN otherwise, login included (docs/04-arquitetura.md
    # §15 "Backend" — found in real QA during Incremento 4.2).
    trusted_browser_origins: tuple[str, ...] = ("http://localhost:5173",)

    # Consulta de CEP (autofill de endereço) — sem chave, mas configurável para
    # apontar a um stub em ambiente de teste sem tocar código.
    viacep_base_url: str = "https://viacep.com.br"
    viacep_timeout_seconds: float = 3.0

    # Rate limit de login — achado em teste manual adversarial (ADR-007): sem
    # isso, o endpoint aceitava tentativas de senha ilimitadas. Persistido no
    # PostgreSQL (login_failures), nunca em memória de processo — a app roda
    # como Function stateless (rule: AGENTS.md, "Vercel é stateless").
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_minutes: int = 15

    @model_validator(mode="after")
    def require_vite_origin_in_development(self) -> Settings:
        if self.env == "dev" and "http://localhost:5173" not in self.trusted_browser_origins:
            raise ValueError(
                "TRUSTED_BROWSER_ORIGINS precisa incluir http://localhost:5173 em desenvolvimento."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # database_url comes from the environment
