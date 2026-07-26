"""Integração com PostgreSQL real (Testcontainers) — vínculo N:N
veterinário-clínica: link, unlink, idempotência, autorização e a regra
"não autônomo exige ao menos uma clínica", ponta a ponta via HTTPX/ASGI.
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
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_TECHNICAL
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
        session.execute(text("DELETE FROM veterinarian_clinics"))
        session.execute(text("DELETE FROM veterinarians"))
        session.execute(text("DELETE FROM clinics"))
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


async def _login_admin(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")


async def _create_clinic(client: httpx.AsyncClient, name: str) -> str:
    response = await client.post("/api/v1/clinics", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["id"])


async def _create_veterinarian(
    client: httpx.AsyncClient,
    *,
    name: str,
    crmv: str,
    # Autonomous by default: most tests here exercise the link/unlink
    # endpoints as a separate step and don't care about the "non-autonomous
    # needs >=1 clinic at creation" rule, which has its own dedicated tests
    # in test_veterinarians_api.py.
    is_autonomous: bool = True,
    clinic_ids: list[str] | None = None,
) -> str:
    response = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": name,
            "crmv": crmv,
            "is_autonomous": is_autonomous,
            "clinic_ids": clinic_ids or [],
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_link_veterinarian_to_clinic_reflects_bidirectionally(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567"
    )

    link_response = await client.post(
        f"/api/v1/veterinarians/{veterinarian_id}/clinics",
        json={"clinic_id": clinic_id, "primary": True},
    )
    assert link_response.status_code == 204

    vet_detail = await client.get(f"/api/v1/veterinarians/{veterinarian_id}")
    assert vet_detail.status_code == 200
    assert vet_detail.json()["clinics"] == [
        {"clinic_id": clinic_id, "clinic_name": "Schweitzer", "primary_clinic": True}
    ]

    clinic_detail = await client.get(f"/api/v1/clinics/{clinic_id}")
    assert clinic_detail.status_code == 200
    assert clinic_detail.json()["veterinarians"] == [
        {
            "veterinarian_id": veterinarian_id,
            "veterinarian_name": "Dra. Fabianna Garcia",
            "crmv": "CRMV-SC 04567",
            "primary_clinic": True,
        }
    ]


async def test_link_veterinarian_to_clinic_is_idempotent(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567"
    )

    payload = {"clinic_id": clinic_id, "primary": False}
    first = await client.post(f"/api/v1/veterinarians/{veterinarian_id}/clinics", json=payload)
    second = await client.post(f"/api/v1/veterinarians/{veterinarian_id}/clinics", json=payload)
    assert first.status_code == 204
    assert second.status_code == 204

    vet_detail = await client.get(f"/api/v1/veterinarians/{veterinarian_id}")
    assert len(vet_detail.json()["clinics"]) == 1


async def test_unlink_veterinarian_from_clinic(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(
        client, name="Karin Witt", crmv="CRMV-SC 04127", is_autonomous=True
    )
    await client.post(
        f"/api/v1/veterinarians/{veterinarian_id}/clinics",
        json={"clinic_id": clinic_id, "primary": False},
    )

    unlink_response = await client.delete(
        f"/api/v1/veterinarians/{veterinarian_id}/clinics/{clinic_id}"
    )
    assert unlink_response.status_code == 204

    vet_detail = await client.get(f"/api/v1/veterinarians/{veterinarian_id}")
    assert vet_detail.json()["clinics"] == []


async def test_unlink_last_clinic_of_non_autonomous_veterinarian_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(
        client,
        name="Eberton Henrique",
        crmv="CRMV-SC 08915",
        is_autonomous=False,
        clinic_ids=[clinic_id],
    )

    unlink_response = await client.delete(
        f"/api/v1/veterinarians/{veterinarian_id}/clinics/{clinic_id}"
    )
    assert unlink_response.status_code == 409

    vet_detail = await client.get(f"/api/v1/veterinarians/{veterinarian_id}")
    assert len(vet_detail.json()["clinics"]) == 1


async def test_link_veterinarian_to_clinic_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567"
    )

    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="technical@vertere.local", password="s3nhaForte!")

    response = await client.post(
        f"/api/v1/veterinarians/{veterinarian_id}/clinics",
        json={"clinic_id": clinic_id, "primary": False},
    )
    assert response.status_code == 403
