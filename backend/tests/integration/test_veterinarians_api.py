"""Integração com PostgreSQL real (Testcontainers) — CRUD, autorização,
CRMV duplicado e soft delete, ponta a ponta via HTTPX/ASGI.
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
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_RECEPTION, ROLE_TECHNICAL
from app.shared.infrastructure.database import build_engine, build_session_factory

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


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
        session.execute(text("DELETE FROM veterinarians"))
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


async def test_create_veterinarian_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )

    await _login(client, email="technical@vertere.local", password="s3nhaForte!")
    response = await client.post(
        "/api/v1/veterinarians", json={"name": "Vet Sem Permissão", "crmv": "CRMV-SC 00001"}
    )

    assert response.status_code == 403


async def test_reception_can_create_veterinarians(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="reception@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )

    await _login(client, email="reception@vertere.local", password="s3nhaForte!")
    response = await client.post(
        "/api/v1/veterinarians", json={"name": "Dra. Fabianna Garcia", "crmv": "CRMV-SC 04567"}
    )

    assert response.status_code == 201


async def test_create_and_get_veterinarian(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    create_response = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": "Dra. Fabianna Garcia",
            "crmv": "crmv-sc 04567",
            "phone": "(47) 9 9914-6833",
            "email": "fabianna@vertere.local",
            "is_autonomous": True,
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "Dra. Fabianna Garcia"
    assert body["crmv"] == "CRMV-SC 04567"
    assert body["is_autonomous"] is True
    assert body["status"] == "ACTIVE"

    get_response = await client.get(f"/api/v1/veterinarians/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Dra. Fabianna Garcia"


async def test_create_veterinarian_with_duplicate_crmv_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    payload = {"name": "Vet A", "crmv": "CRMV-SC 04567"}
    first = await client.post("/api/v1/veterinarians", json=payload)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/veterinarians", json={"name": "Vet B", "crmv": "CRMV-SC 04567"}
    )
    assert second.status_code == 409


async def test_update_veterinarian_with_stale_row_version_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    create_response = await client.post(
        "/api/v1/veterinarians", json={"name": "Vet Bicho Urbano", "crmv": "CRMV-SC 04568"}
    )
    veterinarian_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/veterinarians/{veterinarian_id}",
        json={
            "name": "Vet Bicho Urbano Renomeado",
            "crmv": "CRMV-SC 04568",
            "status": "ACTIVE",
            "expected_row_version": 99,
        },
    )
    assert update_response.status_code == 409


async def test_deactivate_veterinarian_preserves_record(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    create_response = await client.post(
        "/api/v1/veterinarians", json={"name": "Vet Reale", "crmv": "CRMV-SC 04569"}
    )
    veterinarian_id = create_response.json()["id"]

    deactivate_response = await client.post(f"/api/v1/veterinarians/{veterinarian_id}/deactivate")
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["status"] == "INACTIVE"

    get_response = await client.get(f"/api/v1/veterinarians/{veterinarian_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Vet Reale"


async def test_list_veterinarians_without_session_is_unauthenticated(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/veterinarians")
    assert response.status_code == 401
