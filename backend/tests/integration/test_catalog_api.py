"""Integração com PostgreSQL real (Testcontainers) — CRUD de categorias de
exame e de exames (com preço e espécies), ponta a ponta via HTTPX/ASGI.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from decimal import Decimal
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
from app.modules.identity.infrastructure.seed import ROLE_FINANCE, ROLE_LAB_ADMIN, ROLE_TECHNICAL
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
        session.execute(text("DELETE FROM exam_species"))
        session.execute(text("DELETE FROM exams"))
        session.execute(text("DELETE FROM exam_categories"))
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


async def test_create_exam_category_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="technical@vertere.local", password="s3nhaForte!")

    response = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})

    assert response.status_code == 403


async def test_finance_can_create_exam_categories(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="finance@vertere.local", password="s3nhaForte!", role_id=ROLE_FINANCE
    )
    await _login(client, email="finance@vertere.local", password="s3nhaForte!")

    response = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})

    assert response.status_code == 201


async def test_create_and_get_exam_category(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    create_response = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "Hematologia"
    assert body["status"] == "ACTIVE"

    get_response = await client.get(f"/api/v1/exam-categories/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Hematologia"


async def test_create_exam_category_with_duplicate_name_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    first = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})
    assert first.status_code == 201

    second = await client.post("/api/v1/exam-categories", json={"name": "hematologia"})
    assert second.status_code == 409


async def test_update_exam_category_with_stale_row_version_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    create_response = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})
    body = create_response.json()

    response = await client.patch(
        f"/api/v1/exam-categories/{body['id']}",
        json={
            "name": "Hematologia Atualizada",
            "status": "ACTIVE",
            "expected_row_version": body["row_version"] + 1,
        },
    )

    assert response.status_code == 409


async def test_deactivate_exam_category_preserves_record(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    create_response = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})
    body = create_response.json()

    response = await client.post(f"/api/v1/exam-categories/{body['id']}/deactivate")

    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"
    assert response.json()["name"] == "Hematologia"


async def test_list_active_exam_categories_excludes_inactive(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    active = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})
    inactive = await client.post("/api/v1/exam-categories", json={"name": "Descontinuada"})
    await client.post(f"/api/v1/exam-categories/{inactive.json()['id']}/deactivate")

    response = await client.get("/api/v1/exam-categories/active")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["Hematologia"]
    assert active.json()["name"] in names


async def _create_category(client: httpx.AsyncClient, *, name: str = "Hematologia") -> str:
    response = await client.post("/api/v1/exam-categories", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_create_exam_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Cão")
    category_id = await _create_category(client)

    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="technical@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/exams",
        json={
            "code": "HEM001",
            "name": "Hemograma completo",
            "category_id": category_id,
            "price_base": "85.00",
            "species_ids": [species_id],
        },
    )

    assert response.status_code == 403


async def test_create_and_get_exam_with_price_visible_to_pricing_read(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Cão")
    category_id = await _create_category(client)

    create_response = await client.post(
        "/api/v1/exams",
        json={
            "code": "hem001",
            "name": "Hemograma completo",
            "category_id": category_id,
            "price_base": "85.00",
            "plantao_surcharge_percent": "20",
            "species_ids": [species_id],
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["code"] == "HEM001"
    assert Decimal(body["price_base"]) == Decimal("85.00")
    assert Decimal(body["plantao_surcharge_percent"]) == Decimal("20")

    get_response = await client.get(f"/api/v1/exams/{body['id']}")
    assert get_response.status_code == 200
    assert Decimal(get_response.json()["price_base"]) == Decimal("85.00")


async def test_exam_price_hidden_without_pricing_read(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Cão")
    category_id = await _create_category(client)
    create_response = await client.post(
        "/api/v1/exams",
        json={
            "code": "HEM001",
            "name": "Hemograma completo",
            "category_id": category_id,
            "price_base": "85.00",
            "species_ids": [species_id],
        },
    )
    exam_id = create_response.json()["id"]

    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="technical@vertere.local", password="s3nhaForte!")

    response = await client.get(f"/api/v1/exams/{exam_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["price_base"] is None
    assert body["plantao_surcharge_fixed"] is None
    assert body["plantao_surcharge_percent"] is None


async def test_create_exam_with_duplicate_code_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Cão")
    category_id = await _create_category(client)
    payload = {
        "code": "HEM001",
        "name": "Hemograma completo",
        "category_id": category_id,
        "price_base": "85.00",
        "species_ids": [species_id],
    }

    first = await client.post("/api/v1/exams", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/exams", json={**payload, "code": "hem001", "name": "Outro"})
    assert second.status_code == 409


async def test_create_exam_with_both_surcharge_types_is_rejected(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Cão")
    category_id = await _create_category(client)

    response = await client.post(
        "/api/v1/exams",
        json={
            "code": "HEM001",
            "name": "Hemograma completo",
            "category_id": category_id,
            "price_base": "85.00",
            "plantao_surcharge_fixed": "10.00",
            "plantao_surcharge_percent": "20",
            "species_ids": [species_id],
        },
    )

    assert response.status_code == 422


async def test_deactivate_exam_preserves_record(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    species_id = _get_species_id(session_factory, name="Cão")
    category_id = await _create_category(client)
    create_response = await client.post(
        "/api/v1/exams",
        json={
            "code": "HEM001",
            "name": "Hemograma completo",
            "category_id": category_id,
            "price_base": "85.00",
            "species_ids": [species_id],
        },
    )
    exam_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/exams/{exam_id}/deactivate")

    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"
    assert response.json()["name"] == "Hemograma completo"


async def test_import_exams_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="technical@vertere.local", password="s3nhaForte!")

    csv_content = "code,name,category,price_base,species\nHEM001,Hemograma,Hematologia,85.00,Cão\n"
    response = await client.post(
        "/api/v1/exams/import",
        files={"file": ("exams.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 403


async def test_import_exams_partial_success_reports_row_errors(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    await _create_category(client, name="Hematologia")

    csv_content = (
        "code,name,category,price_base,species\n"
        "HEM001,Hemograma completo,Hematologia,85.00,Cão\n"
        "HEM002,Bioquímico,Categoria Inexistente,120.00,Gato\n"
    )
    response = await client.post(
        "/api/v1/exams/import",
        files={"file": ("exams.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["line"] == 3
    assert "Categoria Inexistente" in body["errors"][0]["message"]

    list_response = await client.get("/api/v1/exams", params={"search": "HEM001"})
    assert list_response.json()["total"] == 1


async def test_import_exams_rejects_non_csv_file(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/exams/import",
        files={"file": ("exams.txt", "code,name\n", "text/plain")},
    )

    assert response.status_code == 422


async def test_filter_exams_by_species(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    dog_id = _get_species_id(session_factory, name="Cão")
    cat_id = _get_species_id(session_factory, name="Gato")
    category_id = await _create_category(client)

    await client.post(
        "/api/v1/exams",
        json={
            "code": "HEM001",
            "name": "Hemograma canino",
            "category_id": category_id,
            "price_base": "85.00",
            "species_ids": [dog_id],
        },
    )
    await client.post(
        "/api/v1/exams",
        json={
            "code": "HEM002",
            "name": "Hemograma felino",
            "category_id": category_id,
            "price_base": "90.00",
            "species_ids": [cat_id],
        },
    )

    response = await client.get("/api/v1/exams", params={"species_id": cat_id})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Hemograma felino"
