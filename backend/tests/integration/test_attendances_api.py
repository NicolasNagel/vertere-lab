"""Integração com PostgreSQL real (Testcontainers) — criação de rascunho de
atendimento, confirmação com protocolo/itens financeiros, listagem, leitura
e autorização, ponta a ponta via HTTPX/ASGI.
"""

from __future__ import annotations

import asyncio
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
    """`.claude/rules/12-attendance.md`: todo id é revalidado — um veterinário
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
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
            "service_date": "2026-01-10",
        },
    )
    await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": other_clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
            "service_date": "2026-02-10",
        },
    )

    response = await client.get("/api/v1/attendances", params={"clinic_id": clinic_id})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["clinic_id"] == clinic_id

    response = await client.get(
        "/api/v1/attendances",
        params={
            "owner_name": "maria sou",
            "service_date_from": "2026-01-01",
            "service_date_to": "2026-01-31",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["clinic_id"] == clinic_id

    invalid_range = await client.get(
        "/api/v1/attendances",
        params={"service_date_from": "2026-02-01", "service_date_to": "2026-01-01"},
    )
    assert invalid_range.status_code == 422
    assert invalid_range.json()["error"]["code"] == "VALIDATION_ERROR"


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


async def _create_exam_category(client: httpx.AsyncClient, name: str) -> str:
    response = await client.post("/api/v1/exam-categories", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["id"])


async def _create_exam(
    client: httpx.AsyncClient,
    *,
    code: str,
    category_id: str,
    price_base: str,
    species_ids: list[str],
    plantao_surcharge_percent: str | None = None,
) -> str:
    response = await client.post(
        "/api/v1/exams",
        json={
            "code": code,
            "name": "Hemograma",
            "category_id": category_id,
            "price_base": price_base,
            "species_ids": species_ids,
            "plantao_surcharge_percent": plantao_surcharge_percent,
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _idempotency_header(key: str) -> dict[str, str]:
    return {"Idempotency-Key": key}


async def _create_confirmable_draft(
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    *,
    service_level: str = "NORMAL",
    plantao_surcharge_percent: str | None = None,
) -> tuple[str, str]:
    """Returns (attendance_id, exam_id) for a DRAFT ready to confirm."""
    unique = uuid4().hex[:8]
    clinic_id = await _create_clinic(client, f"Schweitzer {unique}")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv=f"CRMV-SC {unique}"
    )
    patient_id = await _create_patient(client, session_factory)
    species_id = _get_species_id(session_factory, name="Canino")
    category_id = await _create_exam_category(client, f"Hematologia {unique}")
    exam_id = await _create_exam(
        client,
        code=f"HEMO-{unique}",
        category_id=category_id,
        price_base="100.00",
        species_ids=[species_id],
        plantao_surcharge_percent=plantao_surcharge_percent,
    )

    draft_response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
            "service_date": "2026-01-05",
            "service_level": service_level,
        },
    )
    assert draft_response.status_code == 201
    return draft_response.json()["id"], exam_id


async def test_preview_attendance_succeeds_without_persisting(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview",
        json={"items": [{"exam_id": exam_id, "quantity": 2}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attendance_id"] == attendance_id
    assert Decimal(body["grand_total"]) == Decimal("200.00")
    assert Decimal(body["subtotal"]) == Decimal("200.00")
    assert "protocol_number" not in body
    assert "status" not in body

    get_response = await client.get(f"/api/v1/attendances/{attendance_id}")
    assert get_response.json()["status"] == "DRAFT"
    assert get_response.json()["items"] == []

    with session_factory() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM attendance_exams WHERE attendance_id = :id"),
            {"id": attendance_id},
        ).scalar_one()
        assert count == 0
        sequence_count = session.execute(
            text("SELECT COUNT(*) FROM attendance_sequences")
        ).scalar_one()
        assert sequence_count == 0
        audit_count = session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE entity_id = :id"), {"id": attendance_id}
        ).scalar_one()
        assert audit_count == 1  # only the draft_created entry, nothing from preview


async def test_preview_attendance_matches_confirm_totals(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    payload = {"items": [{"exam_id": exam_id, "quantity": 3}]}

    preview_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview", json=payload
    )
    confirm_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json=payload,
        headers=_idempotency_header("preview-then-confirm"),
    )

    assert preview_response.status_code == 200
    assert confirm_response.status_code == 200
    assert preview_response.json()["grand_total"] == confirm_response.json()["grand_total"]
    assert preview_response.json()["subtotal"] == confirm_response.json()["subtotal"]


async def test_preview_attendance_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    await client.post("/api/v1/auth/logout")
    _create_user(
        session_factory,
        email="finance@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_FINANCE,
    )
    await _login(client, email="finance@vertere.local", password="s3nhaForte!")

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
    )

    assert response.status_code == 403


async def test_preview_attendance_does_not_require_idempotency_key(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Preview is read-only — it is not one of the "criação/confirmação/
    fechamento" POSTs the Idempotency-Key rule targets
    (`.claude/rules/02-backend.md`)."""
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
    )

    assert response.status_code == 200


async def test_preview_attendance_unknown_attendance_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{uuid4()}/preview",
        json={"items": [{"exam_id": str(uuid4()), "quantity": 1}]},
    )

    assert response.status_code == 404


async def test_preview_rejects_exam_without_price_valid_on_service_date(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    with session_factory.begin() as session:
        session.execute(
            text("UPDATE exams SET price_valid_from = DATE '2026-02-01' WHERE id = :id"),
            {"id": exam_id},
        )

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PRICE_NOT_AVAILABLE"


async def test_preview_attendance_already_confirmed_is_invalid(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("preview-already-confirmed"),
    )

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
    )

    assert response.status_code == 422


async def test_confirm_attendance_succeeds_with_protocol_and_totals(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 2}]},
        headers=_idempotency_header("confirm-1"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CONFIRMED"
    assert Decimal(body["grand_total"]) == Decimal("200.00")
    assert Decimal(body["subtotal"]) == Decimal("200.00")
    assert body["billing_competence"] == "2026-01-01"
    assert body["protocol_number"] == "2026/000001"
    assert len(body["items"]) == 1
    assert Decimal(body["items"][0]["total_amount"]) == Decimal("200.00")


async def test_on_call_attendance_applies_catalog_surcharge(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(
        client,
        session_factory,
        service_level="ON_CALL",
        plantao_surcharge_percent="25.00",
    )

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 2}]},
        headers=_idempotency_header("confirm-on-call"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["service_level"] == "ON_CALL"
    assert Decimal(body["surcharge_total"]) == Decimal("50.00")
    assert Decimal(body["grand_total"]) == Decimal("250.00")

    with session_factory() as session:
        row = session.execute(
            text(
                "SELECT action, entity_id FROM audit_log "
                "WHERE action = 'attendances.confirmed' ORDER BY occurred_at DESC LIMIT 1"
            )
        ).one()
        assert row.entity_id == attendance_id


async def test_confirm_attendance_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    await client.post("/api/v1/auth/logout")
    _create_user(
        session_factory,
        email="finance@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_FINANCE,
    )
    await _login(client, email="finance@vertere.local", password="s3nhaForte!")

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("confirm-forbidden"),
    )

    assert response.status_code == 403


async def test_confirm_attendance_twice_is_invalid(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Two DIFFERENT Idempotency-Keys, same attendance: this must fail on
    the domain state machine (already CONFIRMED), not be swallowed by
    idempotency replay — that behavior is covered separately by
    ``test_confirm_attendance_same_key_and_payload_replays_previous_response``.
    """
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    first = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("confirm-twice-1"),
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("confirm-twice-2"),
    )
    assert second.status_code == 422


async def test_confirm_attendance_same_key_and_payload_replays_previous_response(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    payload = {"items": [{"exam_id": exam_id, "quantity": 1}]}

    first = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json=payload,
        headers=_idempotency_header("confirm-replay"),
    )
    second = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json=payload,
        headers=_idempotency_header("confirm-replay"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    with session_factory() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM attendance_exams WHERE attendance_id = :id"),
            {"id": attendance_id},
        ).scalar_one()
        assert count == 1


async def test_confirm_attendance_same_key_different_payload_is_conflict(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    first = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("confirm-conflict"),
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 2}]},
        headers=_idempotency_header("confirm-conflict"),
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


async def test_confirm_attendance_without_idempotency_key_is_validation_error(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
    )

    assert response.status_code == 422


async def test_confirm_attendance_concurrent_same_key_confirms_exactly_once(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Real concurrency (`.claude/rules/08-testing.md`: "concorrência real
    testada de verdade") — double-click sends the same Idempotency-Key
    twice at once. Exactly one CONFIRMED attendance with one protocol must
    result; the loser gets either the replayed 200 or a safe 409, never a
    second protocol number or a 500.
    """
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    payload = {"items": [{"exam_id": exam_id, "quantity": 1}]}
    headers = _idempotency_header("confirm-concurrent")

    responses = await asyncio.gather(
        client.post(f"/api/v1/attendances/{attendance_id}/confirm", json=payload, headers=headers),
        client.post(f"/api/v1/attendances/{attendance_id}/confirm", json=payload, headers=headers),
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses in ([200, 200], [200, 409])

    with session_factory() as session:
        row = session.execute(
            text("SELECT status, protocol_number FROM attendances WHERE id = :id"),
            {"id": attendance_id},
        ).one()
        assert row.status == "CONFIRMED"
        assert row.protocol_number == "2026/000001"
        item_count = session.execute(
            text("SELECT COUNT(*) FROM attendance_exams WHERE attendance_id = :id"),
            {"id": attendance_id},
        ).scalar_one()
        assert item_count == 1


async def test_confirm_attendance_without_items_is_invalid(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": []},
        headers=_idempotency_header("confirm-no-items"),
    )

    assert response.status_code == 422


async def test_confirm_attendance_unknown_attendance_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{uuid4()}/confirm",
        json={"items": [{"exam_id": str(uuid4()), "quantity": 1}]},
        headers=_idempotency_header("confirm-unknown"),
    )

    assert response.status_code == 404


async def test_confirm_attendance_protocol_sequence_increments_across_clinics(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Protocol is a lab-wide sequence per year, not per clinic
    (`docs/03-modelo-de-dominio.md` §7: `UNIQUE(protocol_year,
    protocol_sequence)`, no `clinic_id` in the constraint)."""
    await _login_admin(client, session_factory)
    first_attendance_id, first_exam_id = await _create_confirmable_draft(client, session_factory)
    second_attendance_id, second_exam_id = await _create_confirmable_draft(client, session_factory)

    first = await client.post(
        f"/api/v1/attendances/{first_attendance_id}/confirm",
        json={"items": [{"exam_id": first_exam_id, "quantity": 1}]},
        headers=_idempotency_header("confirm-seq-1"),
    )
    second = await client.post(
        f"/api/v1/attendances/{second_attendance_id}/confirm",
        json={"items": [{"exam_id": second_exam_id, "quantity": 1}]},
        headers=_idempotency_header("confirm-seq-2"),
    )

    assert first.json()["protocol_number"] == "2026/000001"
    assert second.json()["protocol_number"] == "2026/000002"


async def test_cancel_draft_attendance_succeeds_and_audits(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Tutor desmarcou o exame"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["cancel_reason"] == "Tutor desmarcou o exame"

    with session_factory() as session:
        row = session.execute(
            text(
                "SELECT action, entity_id, reason FROM audit_log "
                "WHERE action = 'attendances.cancelled' ORDER BY occurred_at DESC LIMIT 1"
            )
        ).one()
        assert row.entity_id == attendance_id
        assert row.reason == "Tutor desmarcou o exame"


async def test_cancel_confirmed_attendance_succeeds(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    confirm_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("cancel-after-confirm"),
    )
    assert confirm_response.status_code == 200

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Erro de cadastro"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


async def test_cancel_attendance_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    await client.post("/api/v1/auth/logout")
    _create_user(
        session_factory,
        email="finance-cancel@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_FINANCE,
    )
    await _login(client, email="finance-cancel@vertere.local", password="s3nhaForte!")

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Tentativa sem permissão"},
    )

    assert response.status_code == 403


async def test_cancel_attendance_unknown_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{uuid4()}/cancel",
        json={"reason": "Não deveria existir"},
    )

    assert response.status_code == 404


async def test_cancel_attendance_without_reason_is_validation_error(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": ""},
    )

    assert response.status_code == 422


async def test_cancel_attendance_twice_is_conflict(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)
    first = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Primeiro cancelamento"},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Segundo cancelamento"},
    )

    assert second.status_code == 409


async def test_cancel_attendance_rejects_mass_assignment(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Motivo válido", "status": "CONFIRMED", "grand_total": "0.00"},
    )

    assert response.status_code == 422


async def test_update_draft_attendance_notes_succeeds_and_audits(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": 1, "notes": "Paciente agitado"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["notes"] == "Paciente agitado"
    assert body["row_version"] == 2

    with session_factory() as session:
        row = session.execute(
            text(
                "SELECT action, entity_id FROM audit_log "
                "WHERE action = 'attendances.updated' ORDER BY occurred_at DESC LIMIT 1"
            )
        ).one()
        assert row.entity_id == attendance_id


async def test_update_attendance_wrong_row_version_is_conflict(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": 999, "notes": "Não deveria passar"},
    )

    assert response.status_code == 409


async def test_update_attendance_uses_current_row_version_after_first_edit(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Two sequential edits with a stale `row_version` each: the second
    must be rejected even though it isn't a truly concurrent write —
    `expected_row_version` in the request body catches this
    (`.claude/rules/05-frontend-web-mobile.md`: "conflito de versão oferece recarregar,
    nunca sobrescreve silenciosamente")."""
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    first = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": 1, "notes": "Primeira edição"},
    )
    assert first.status_code == 200
    assert first.json()["row_version"] == 2

    stale_retry = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": 1, "notes": "Edição com versão desatualizada"},
    )
    assert stale_retry.status_code == 409

    second = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": 2, "notes": "Segunda edição, com a versão certa"},
    )
    assert second.status_code == 200
    assert second.json()["notes"] == "Segunda edição, com a versão certa"
    assert second.json()["row_version"] == 3


async def test_update_confirmed_attendance_clinic_is_rejected(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    confirm_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("update-confirmed-clinic"),
    )
    assert confirm_response.status_code == 200
    row_version = confirm_response.json()["row_version"]

    response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": row_version, "clinic_id": str(uuid4())},
    )

    assert response.status_code == 422


async def test_update_confirmed_attendance_notes_succeeds(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    confirm_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("update-confirmed-notes"),
    )
    assert confirm_response.status_code == 200
    row_version = confirm_response.json()["row_version"]

    response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": row_version, "notes": "Retorno em 7 dias"},
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Retorno em 7 dias"
    assert response.json()["status"] == "CONFIRMED"


async def test_update_attendance_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    await client.post("/api/v1/auth/logout")
    _create_user(
        session_factory,
        email="finance-update@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_FINANCE,
    )
    await _login(client, email="finance-update@vertere.local", password="s3nhaForte!")

    response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": 1, "notes": "Tentativa sem permissão"},
    )

    assert response.status_code == 403


async def test_update_attendance_unknown_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.patch(
        f"/api/v1/attendances/{uuid4()}",
        json={"row_version": 1, "notes": "Não deveria existir"},
    )

    assert response.status_code == 404


async def test_update_attendance_rejects_mass_assignment(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)

    response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": 1, "notes": "Ok", "grand_total": "0.00", "status": "CONFIRMED"},
    )

    assert response.status_code == 422


async def test_update_cancelled_attendance_is_conflict(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)
    cancel_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Motivo do cancelamento"},
    )
    assert cancel_response.status_code == 200
    row_version = cancel_response.json()["row_version"]

    response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": row_version, "notes": "Não deveria passar"},
    )

    assert response.status_code == 409


async def test_get_attendance_timeline_lists_actions_most_recent_first(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)

    confirm_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers=_idempotency_header("timeline-confirm"),
    )
    assert confirm_response.status_code == 200
    row_version = confirm_response.json()["row_version"]

    update_response = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={"row_version": row_version, "notes": "Retorno agendado"},
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/v1/attendances/{attendance_id}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    actions = [item["action"] for item in body["items"]]
    assert actions == ["attendances.updated", "attendances.confirmed", "attendances.draft_created"]
    assert body["items"][0]["after_state"] == {"notes": "Retorno agendado"}
    assert body["items"][0]["reason"] is None


async def test_get_attendance_timeline_paginates(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)
    row_version = 1
    for i in range(3):
        r = await client.patch(
            f"/api/v1/attendances/{attendance_id}",
            json={"row_version": row_version, "notes": f"Edição {i}"},
        )
        assert r.status_code == 200
        row_version = r.json()["row_version"]

    response = await client.get(
        f"/api/v1/attendances/{attendance_id}/timeline", params={"page": 1, "page_size": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4  # draft_created + 3 updates
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


async def test_get_attendance_timeline_only_includes_this_attendance(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_a, _exam_a = await _create_confirmable_draft(client, session_factory)
    attendance_b, _exam_b = await _create_confirmable_draft(client, session_factory)

    response = await client.get(f"/api/v1/attendances/{attendance_a}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "attendances.draft_created"
    assert attendance_a != attendance_b


async def test_get_attendance_timeline_unknown_attendance_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.get(f"/api/v1/attendances/{uuid4()}/timeline")

    assert response.status_code == 404


async def test_get_attendance_timeline_without_authentication_is_unauthenticated(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, _exam_id = await _create_confirmable_draft(client, session_factory)
    await client.post("/api/v1/auth/logout")

    response = await client.get(f"/api/v1/attendances/{attendance_id}/timeline")

    assert response.status_code == 401
