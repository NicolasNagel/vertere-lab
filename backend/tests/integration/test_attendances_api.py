"""Integração com PostgreSQL real (Testcontainers) — criação de rascunho de
atendimento, listagem, leitura e autorização, ponta a ponta via HTTPX/ASGI.

Esta fatia cobre só `DRAFT` (`app/modules/attendances/domain/entities.py`) —
sem `/confirm`, protocolo ou item financeiro ainda.
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
from app.modules.identity.infrastructure.seed import ROLE_FINANCE, ROLE_LAB_ADMIN, ROLE_RECEPTION
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
        session.execute(text("DELETE FROM attendances"))
        session.execute(text("DELETE FROM veterinarian_clinics"))
        session.execute(text("DELETE FROM patients"))
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


async def _login_reception(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="reception@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )
    await _login(client, email="reception@vertere.local", password="s3nhaForte!")


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


def _get_species_id(session_factory: sessionmaker[Session], *, name: str) -> str:
    with session_factory() as session:
        row = session.execute(
            text("SELECT id FROM species WHERE name = :name"), {"name": name}
        ).one()
        return str(row[0])


async def _create_patient(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> str:
    species_id = _get_species_id(session_factory, name="Cão")
    response = await client.post(
        "/api/v1/patients",
        json={
            "name": "Rex",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_create_attendance_draft_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="finance@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_FINANCE,
    )
    await _login(client, email="finance@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": str(uuid4()),
            "veterinarian_id": str(uuid4()),
            "patient_id": str(uuid4()),
        },
    )

    assert response.status_code == 403


async def test_create_and_get_attendance_draft(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567"
    )
    patient_id = await _create_patient(client, session_factory)

    create_response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
            "service_date": "2026-01-05",
            "notes": "Consulta de rotina",
        },
    )

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["status"] == "DRAFT"
    assert body["clinic_id"] == clinic_id
    assert body["veterinarian_id"] == veterinarian_id
    assert body["patient_id"] == patient_id
    assert body["notes"] == "Consulta de rotina"

    get_response = await client.get(f"/api/v1/attendances/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "DRAFT"


async def test_create_attendance_draft_with_unknown_clinic_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    veterinarian_id = await _create_veterinarian(client, name="Dr. Teste", crmv="CRMV-SC 00001")
    patient_id = await _create_patient(client, session_factory)

    response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": str(uuid4()),
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
        },
    )

    assert response.status_code == 404


async def test_create_attendance_draft_with_non_autonomous_veterinarian_not_linked_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """`.claude/rules/attendence.md`: todo id é revalidado — um veterinário
    não autônomo sem vínculo com a clínica escolhida não pode originar
    atendimento ali (ADR-003)."""
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    other_clinic_id = await _create_clinic(client, "VetCenter")
    veterinarian_id = await _create_veterinarian(
        client,
        name="Eberton Henrique",
        crmv="CRMV-SC 08915",
        is_autonomous=False,
        clinic_ids=[other_clinic_id],
    )
    patient_id = await _create_patient(client, session_factory)

    response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
        },
    )

    assert response.status_code == 422


async def test_create_attendance_draft_with_inactive_patient_is_invalid(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(client, name="Dr. Teste", crmv="CRMV-SC 00001")
    patient_id = await _create_patient(client, session_factory)
    deactivate_response = await client.post(f"/api/v1/patients/{patient_id}/deactivate")
    assert deactivate_response.status_code == 200

    response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
        },
    )

    assert response.status_code == 422


async def test_reception_creates_attendance_draft_and_it_is_audited(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(client, name="Dr. Teste", crmv="CRMV-SC 00001")
    patient_id = await _create_patient(client, session_factory)

    await client.post("/api/v1/auth/logout")
    await _login_reception(client, session_factory)

    response = await client.post(
        "/api/v1/attendances/drafts",
        json={"clinic_id": clinic_id, "veterinarian_id": veterinarian_id, "patient_id": patient_id},
    )
    assert response.status_code == 201
    attendance_id = response.json()["id"]

    with session_factory() as session:
        row = session.execute(
            text(
                "SELECT action, entity_id FROM audit_log "
                "WHERE action = 'attendances.draft_created' ORDER BY occurred_at DESC LIMIT 1"
            )
        ).one()
        assert row.entity_id == attendance_id


async def test_list_attendances_filters_by_clinic(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    other_clinic_id = await _create_clinic(client, "VetCenter")
    veterinarian_id = await _create_veterinarian(client, name="Dr. Teste", crmv="CRMV-SC 00001")
    patient_id = await _create_patient(client, session_factory)

    await client.post(
        "/api/v1/attendances/drafts",
        json={"clinic_id": clinic_id, "veterinarian_id": veterinarian_id, "patient_id": patient_id},
    )
    await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": other_clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
        },
    )

    response = await client.get("/api/v1/attendances", params={"clinic_id": clinic_id})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["clinic_id"] == clinic_id


async def test_get_attendance_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.get(f"/api/v1/attendances/{uuid4()}")

    assert response.status_code == 404


async def test_list_attendances_without_authentication_is_unauthenticated(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/attendances")
    assert response.status_code == 401
