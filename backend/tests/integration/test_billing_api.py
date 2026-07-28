"""Integração com PostgreSQL real (Testcontainers) — GET /closures/preview
ponta a ponta via HTTPX/ASGI.

Esta fatia cobre só a prévia (Incremento 4.1) — read-only, sem persistência
(`.claude/rules/monthly-closure.md`).
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
        session.execute(text("DELETE FROM attendance_exams"))
        session.execute(text("DELETE FROM attendances"))
        session.execute(text("DELETE FROM attendance_sequences"))
        session.execute(text("DELETE FROM exams"))
        session.execute(text("DELETE FROM exam_categories"))
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


async def _login_admin(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")


def _get_species_id(session_factory: sessionmaker[Session], *, name: str) -> str:
    with session_factory() as session:
        row = session.execute(
            text("SELECT id FROM species WHERE name = :name"), {"name": name}
        ).one()
        return str(row[0])


async def _create_clinic(client: httpx.AsyncClient, name: str) -> str:
    response = await client.post("/api/v1/clinics", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["id"])


async def _create_veterinarian(client: httpx.AsyncClient, *, name: str, crmv: str) -> str:
    response = await client.post(
        "/api/v1/veterinarians",
        json={"name": name, "crmv": crmv, "is_autonomous": True, "clinic_ids": []},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _create_patient(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> str:
    species_id = _get_species_id(session_factory, name="Canino")
    response = await client.post(
        "/api/v1/patients",
        json={"name": "Rex", "species_id": species_id, "sex": "MALE", "owner_name": "Maria Souza"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _create_exam(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, code: str, price: str
) -> str:
    species_id = _get_species_id(session_factory, name="Canino")
    category_response = await client.post("/api/v1/exam-categories", json={"name": f"Cat {code}"})
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]
    response = await client.post(
        "/api/v1/exams",
        json={
            "code": code,
            "name": "Hemograma",
            "category_id": category_id,
            "price_base": price,
            "species_ids": [species_id],
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _confirm_attendance(
    client: httpx.AsyncClient,
    *,
    clinic_id: str,
    veterinarian_id: str,
    patient_id: str,
    exam_id: str,
    service_date: str,
    quantity: int = 1,
) -> dict[str, object]:
    draft_response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
            "service_date": service_date,
        },
    )
    assert draft_response.status_code == 201
    attendance_id = draft_response.json()["id"]

    confirm_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": quantity}]},
    )
    assert confirm_response.status_code == 200
    body: dict[str, object] = confirm_response.json()
    return body


async def test_preview_returns_eligible_and_blocked_items_with_correct_totals(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    vet_id = await _create_veterinarian(client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567")
    patient_id = await _create_patient(client, session_factory)
    exam_id = await _create_exam(client, session_factory, code="HEMO-001", price="100.00")

    eligible_1 = await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-05",
        quantity=2,
    )
    eligible_2 = await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-20",
    )
    # Fora da competência (fevereiro) — não deve aparecer na prévia de janeiro.
    await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-02-01",
    )
    # Item cancelado dentro da competência — deve aparecer como bloqueado.
    blocked = await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-10",
    )
    with session_factory() as session:
        session.execute(
            text("UPDATE attendance_exams SET status = 'CANCELLED' WHERE attendance_id = :id"),
            {"id": blocked["id"]},
        )
        session.commit()

    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_id, "year": 2026, "month": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["competence_year"] == 2026
    assert body["competence_month"] == 1
    assert body["period_start"] == "2026-01-01"
    assert body["period_end"] == "2026-01-31"
    assert body["attendance_count"] == 3
    assert body["cancelled_attendance_count"] == 0
    assert body["item_count"] == 2
    assert Decimal(body["subtotal"]) == Decimal("300.00")
    assert Decimal(body["grand_total"]) == Decimal("300.00")

    eligible_ids = {item["attendance_id"] for item in body["eligible_items"]}
    assert eligible_ids == {eligible_1["id"], eligible_2["id"]}

    blocked_ids = {item["attendance_id"] for item in body["blocked_items"]}
    assert blocked["id"] in blocked_ids
    blocked_entry = next(i for i in body["blocked_items"] if i["attendance_id"] == blocked["id"])
    assert blocked_entry["reason"]


async def test_preview_excludes_cancelled_attendance(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    vet_id = await _create_veterinarian(client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567")
    patient_id = await _create_patient(client, session_factory)
    exam_id = await _create_exam(client, session_factory, code="HEMO-001", price="100.00")

    cancelled = await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-05",
    )
    with session_factory() as session:
        session.execute(
            text("UPDATE attendances SET status = 'CANCELLED' WHERE id = :id"),
            {"id": cancelled["id"]},
        )
        session.commit()

    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_id, "year": 2026, "month": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attendance_count"] == 1
    assert body["cancelled_attendance_count"] == 1
    assert body["item_count"] == 0
    assert Decimal(body["grand_total"]) == Decimal("0")
    assert len(body["blocked_items"]) == 1


async def test_preview_isolates_clinics(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_a = await _create_clinic(client, "Schweitzer")
    clinic_b = await _create_clinic(client, "VetCenter")
    vet_id = await _create_veterinarian(client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567")
    patient_id = await _create_patient(client, session_factory)
    exam_id = await _create_exam(client, session_factory, code="HEMO-001", price="100.00")

    await _confirm_attendance(
        client,
        clinic_id=clinic_b,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-05",
    )

    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_a, "year": 2026, "month": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attendance_count"] == 0
    assert body["item_count"] == 0


async def test_preview_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")

    await client.post("/api/v1/auth/logout")
    _create_user(
        session_factory,
        email="reception@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )
    await _login(client, email="reception@vertere.local", password="s3nhaForte!")

    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_id, "year": 2026, "month": 1},
    )

    assert response.status_code == 403


async def test_preview_with_finance_role_succeeds(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")

    await client.post("/api/v1/auth/logout")
    _create_user(
        session_factory, email="finance@vertere.local", password="s3nhaForte!", role_id=ROLE_FINANCE
    )
    await _login(client, email="finance@vertere.local", password="s3nhaForte!")

    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_id, "year": 2026, "month": 1},
    )

    assert response.status_code == 200


async def test_preview_unknown_clinic_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": str(uuid4()), "year": 2026, "month": 1},
    )

    assert response.status_code == 404


async def test_preview_invalid_month_is_validation_error(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")

    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_id, "year": 2026, "month": 13},
    )

    assert response.status_code == 422


async def test_preview_without_authentication_is_unauthenticated(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": str(uuid4()), "year": 2026, "month": 1},
    )
    assert response.status_code == 401


async def test_preview_does_not_persist_anything(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    vet_id = await _create_veterinarian(client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567")
    patient_id = await _create_patient(client, session_factory)
    exam_id = await _create_exam(client, session_factory, code="HEMO-001", price="100.00")
    await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-05",
    )

    def _table_counts() -> dict[str, int]:
        with session_factory() as session:
            return {
                table: session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                for table in ("attendances", "attendance_exams", "audit_log")
            }

    before = _table_counts()
    response = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_id, "year": 2026, "month": 1},
    )
    after = _table_counts()

    assert response.status_code == 200
    assert before == after
