"""Integração com PostgreSQL real (Testcontainers) — catálogo de espécies
seedado pela migration 0007 e CRUD de pacientes (owner embutido), ponta a
ponta via HTTPX/ASGI.
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
        session.execute(text("DELETE FROM patients"))
        session.execute(text("DELETE FROM users"))
        session.commit()


def _get_species_id(session_factory: sessionmaker[Session], *, name: str) -> str:
    with session_factory() as session:
        row = session.execute(
            text("SELECT id FROM species WHERE name = :name"), {"name": name}
        ).one()
        return str(row[0])


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


async def test_list_species_without_authentication_is_unauthenticated(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/species")
    assert response.status_code == 401


async def test_list_species_is_open_to_any_authenticated_role(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Species has no dedicated permission — any authenticated user can read
    it (see `app/modules/patients/application/list_species.py`), since the
    Exam catalog (Fase 2) also needs it and may be used by a role without
    `patients.read` (e.g. pure `FINANCE`)."""
    _create_user(
        session_factory,
        email="finance@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_FINANCE,
    )
    await _login(client, email="finance@vertere.local", password="s3nhaForte!")

    response = await client.get("/api/v1/species")

    assert response.status_code == 200


async def test_reception_lists_seeded_species(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="reception@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )
    await _login(client, email="reception@vertere.local", password="s3nhaForte!")

    response = await client.get("/api/v1/species")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == sorted(names)
    assert {"Canino", "Felino", "Bovino", "Equino", "Coelho", "Caprino"} <= set(names)


async def test_create_patient_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="finance@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_FINANCE,
    )
    await _login(client, email="finance@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Canino")

    response = await client.post(
        "/api/v1/patients",
        json={
            "name": "Rex",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
    )

    assert response.status_code == 403


async def test_create_and_get_patient(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Felino")

    create_response = await client.post(
        "/api/v1/patients",
        json={
            "name": "Mimi",
            "species_id": species_id,
            "sex": "FEMALE",
            "breed": "Siamês",
            "age_description": "3 anos",
            "owner_name": "Joana Lima",
            "owner_phone": "(47) 9 9914-6833",
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "Mimi"
    assert body["owner_name"] == "Joana Lima"
    assert body["status"] == "ACTIVE"

    get_response = await client.get(f"/api/v1/patients/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["owner_name"] == "Joana Lima"


async def test_create_patient_with_unknown_species_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """`species_id` is validated before persisting — an unknown id must
    surface as 404, not as a raw IntegrityError/500 from the FK
    constraint (see app/modules/patients/application/create_patient.py)."""
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/patients",
        json={
            "name": "Rex",
            "species_id": str(uuid4()),
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
    )

    assert response.status_code == 404


async def test_create_patient_allows_duplicate_owner_name(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Canino")
    payload = {
        "name": "Rex",
        "species_id": species_id,
        "sex": "MALE",
        "owner_name": "Maria Souza",
    }

    first = await client.post("/api/v1/patients", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/patients", json={**payload, "name": "Rex II"})
    assert second.status_code == 201


async def test_update_patient_with_stale_row_version_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Canino")

    create_response = await client.post(
        "/api/v1/patients",
        json={
            "name": "Rex",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
    )
    body = create_response.json()

    response = await client.patch(
        f"/api/v1/patients/{body['id']}",
        json={
            "name": "Rex Atualizado",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
            "status": "ACTIVE",
            "expected_row_version": body["row_version"] + 1,
        },
    )

    assert response.status_code == 409


async def test_deactivate_patient_preserves_record(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Canino")

    create_response = await client.post(
        "/api/v1/patients",
        json={
            "name": "Rex",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
    )
    body = create_response.json()

    response = await client.post(f"/api/v1/patients/{body['id']}/deactivate")

    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"
    assert response.json()["name"] == "Rex"


async def test_search_patients_by_owner_name(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Canino")

    await client.post(
        "/api/v1/patients",
        json={
            "name": "Rex",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
    )
    await client.post(
        "/api/v1/patients",
        json={
            "name": "Bidu",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Joana Lima",
        },
    )

    response = await client.get("/api/v1/patients", params={"search": "joana"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Bidu"
