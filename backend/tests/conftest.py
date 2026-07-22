from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    # URL sintética: nenhum teste de API abre conexão (o pool é lazy).
    return Settings(
        env="test",
        log_level="WARNING",
        database_url=SecretStr("postgresql+psycopg://test:test@localhost:5499/test_unused"),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
