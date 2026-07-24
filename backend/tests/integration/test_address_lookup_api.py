"""Integração via HTTPX/ASGI — autenticação real (PostgreSQL/Testcontainers),
provedor ViaCEP substituído por um fake via dependency override (mock só na
fronteira externa, nunca no que está sendo testado — rule: 09-testing.md).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.modules.address_lookup.api.dependencies import get_cep_lookup_port
from app.modules.address_lookup.domain.entities import CepAddress
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN
from app.shared.domain.errors import ExternalServiceUnavailableError
from app.shared.infrastructure.database import build_engine, build_session_factory

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


class _FakeCepLookupPort:
    def __init__(self, *, result: CepAddress | None = None, unavailable: bool = False) -> None:
        self._result = result
        self._unavailable = unavailable

    def lookup(self, cep: str) -> CepAddress | None:
        if self._unavailable:
            raise ExternalServiceUnavailableError("indisponível")
        return self._result


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="module")
def monkeypatch_module() -> Iterator[pytest.MonkeyPatch]:
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module", autouse=True)
def _migrated_schema(postgres_url: str, monkeypatch_module: pytest.MonkeyPatch) -> None:
    monkeypatch_module.setenv("DATABASE_URL", postgres_url)
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "backend" / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture
def session_factory(postgres_url: str) -> Iterator[sessionmaker[Session]]:
    engine = build_engine(postgres_url)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM users"))
        session.commit()


@pytest.fixture
def settings(postgres_url: str) -> Settings:
    return Settings(
        env="test",
        log_level="WARNING",
        database_url=SecretStr(postgres_url),
        session_cookie_secure=False,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as async_client,
        app.router.lifespan_context(app),
    ):
        yield async_client


def _create_user(
    session_factory: sessionmaker[Session], *, email: str, password: str, role_id: UUID
) -> UserModel:
    with session_factory() as session:
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email=email,
            full_name=email,
            password_hash=hash_password(password),
            is_active=True,
            role_id=role_id,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        session.add(LabMembershipModel(id=uuid4(), user_id=user.id, is_active=True, granted_at=now))
        session.commit()
        session.refresh(user)
        return user


async def _login(client: httpx.AsyncClient, *, email: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": password, "remember_me": False},
    )
    assert response.status_code == 200


async def test_lookup_cep_without_session_is_unauthenticated(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/address-lookup/cep/01310100")
    assert response.status_code == 401


async def test_lookup_cep_returns_address(
    app: FastAPI, client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    app.dependency_overrides[get_cep_lookup_port] = lambda: _FakeCepLookupPort(
        result=CepAddress(
            zip_code="01310100",
            street="Avenida Paulista",
            neighborhood="Bela Vista",
            city="São Paulo",
            state="SP",
        )
    )
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.get("/api/v1/address-lookup/cep/01310-100")

    assert response.status_code == 200
    body = response.json()
    assert body["street"] == "Avenida Paulista"
    assert body["city"] == "São Paulo"


async def test_lookup_cep_malformed_is_validation_error(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.get("/api/v1/address-lookup/cep/123")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_lookup_cep_not_found(
    app: FastAPI, client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    app.dependency_overrides[get_cep_lookup_port] = lambda: _FakeCepLookupPort(result=None)
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.get("/api/v1/address-lookup/cep/00000000")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_lookup_cep_provider_unavailable(
    app: FastAPI, client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    app.dependency_overrides[get_cep_lookup_port] = lambda: _FakeCepLookupPort(unavailable=True)
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.get("/api/v1/address-lookup/cep/01310100")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EXTERNAL_SERVICE_UNAVAILABLE"
