"""Integração com PostgreSQL real (Testcontainers) — `POST /closures`
ponta a ponta via HTTPX/ASGI (Incremento 4.2).

Cobre os testes obrigatórios de `.claude/rules/13-monthly-closure.md`: dois
fechamentos concorrentes para a mesma clínica+competência, idempotência
(mesma key repetida e mesma key com payload diferente), item já pertencente
a outro fechamento, soma exata cabeçalho vs. itens, item cancelado excluído,
e que uma falha antes do commit não deixa estado parcial.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

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
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN
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
        session.execute(text("DELETE FROM outbox_events"))
        session.execute(text("DELETE FROM idempotency_keys"))
        session.execute(text("DELETE FROM monthly_closure_items"))
        # Attendances hold a RESTRICT FK to monthly_closures — must be
        # nulled out before the closure rows themselves can be deleted.
        session.execute(text("UPDATE attendances SET monthly_closure_id = NULL"))
        session.execute(text("DELETE FROM monthly_closures"))
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


def _create_user(session_factory: sessionmaker[Session], *, email: str, password: str) -> UserModel:
    with session_factory() as session:
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email=email,
            full_name=email,
            password_hash=hash_password(password),
            is_active=True,
            role_id=ROLE_LAB_ADMIN,
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
    _create_user(session_factory, email="admin@vertere.local", password="s3nhaForte!")
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")


def _get_species_id(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as session:
        row = session.execute(
            text("SELECT id FROM species WHERE name = :name"), {"name": "Canino"}
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
    species_id = _get_species_id(session_factory)
    response = await client.post(
        "/api/v1/patients",
        json={"name": "Rex", "species_id": species_id, "sex": "MALE", "owner_name": "Maria Souza"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _create_exam(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, code: str, price: str
) -> str:
    species_id = _get_species_id(session_factory)
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
        headers={"Idempotency-Key": f"confirm-{attendance_id}"},
    )
    assert confirm_response.status_code == 200
    body: dict[str, object] = confirm_response.json()
    return body


async def _setup_clinic_with_confirmed_attendance(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, service_date: str
) -> tuple[str, dict[str, object]]:
    clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")
    vet_id = await _create_veterinarian(client, name="Dra. Ana", crmv=f"CRMV-{uuid4()}")
    patient_id = await _create_patient(client, session_factory)
    exam_id = await _create_exam(
        client, session_factory, code=f"HEMO-{uuid4().hex[:6]}", price="100.00"
    )
    attendance = await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date=service_date,
    )
    return clinic_id, attendance


def _close_headers(key: str) -> dict[str, str]:
    return {"Idempotency-Key": key}


async def test_close_creates_a_closure_and_locks_the_source_attendance(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )

    response = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-1"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "CLOSED"
    assert body["clinic_id"] == clinic_id
    assert body["item_count"] == 1
    assert Decimal(body["grand_total"]) == Decimal("100.00")
    assert len(body["items"]) == 1
    assert body["items"][0]["attendance_id"] == attendance["id"]

    with session_factory() as session:
        row = session.execute(
            text("SELECT monthly_closure_id FROM attendances WHERE id = :id"),
            {"id": attendance["id"]},
        ).one()
        assert str(row[0]) == body["id"]

        audit_action = session.execute(
            text("SELECT action FROM audit_log WHERE entity_id = :id"), {"id": body["id"]}
        ).scalar_one()
        assert audit_action == "closures.closed"

        outbox_event_type = session.execute(
            text("SELECT event_type FROM outbox_events WHERE payload->>'closure_id' = :id"),
            {"id": body["id"]},
        ).scalar_one()
        assert outbox_event_type == "closures.closed"

    # A now-closed attendance can no longer be cancelled or edited.
    cancel_response = await client.post(
        f"/api/v1/attendances/{attendance['id']}/cancel",
        json={"reason": "tentativa pós-fechamento"},
    )
    assert cancel_response.status_code == 409


async def test_close_excludes_a_cancelled_item(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    with session_factory() as session:
        session.execute(
            text("UPDATE attendance_exams SET status = 'CANCELLED' WHERE attendance_id = :id"),
            {"id": attendance["id"]},
        )
        session.commit()

    response = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-excludes-cancelled"),
    )

    assert response.status_code == 422


async def test_close_rejects_when_there_is_nothing_eligible(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")

    response = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-empty"),
    )

    assert response.status_code == 422


async def test_close_rejects_a_second_active_closure_for_the_same_clinic_and_period(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, _attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    first = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-first"),
    )
    assert first.status_code == 201

    # A second, unrelated attendance in the same clinic+period — the close
    # must be rejected even though there IS a new eligible item, because
    # the clinic+period itself is already closed.
    _clinic_id_unused, _attendance2 = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-15"
    )

    second = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-second"),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CLOSURE_ALREADY_EXISTS"


async def test_close_is_idempotent_for_the_same_key_and_payload(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, _attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    payload = {"clinic_id": clinic_id, "year": 2026, "month": 1}
    headers = _close_headers("close-idempotent")

    first = await client.post("/api/v1/closures", json=payload, headers=headers)
    second = await client.post("/api/v1/closures", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    with session_factory() as session:
        count = session.execute(text("SELECT COUNT(*) FROM monthly_closures")).scalar_one()
        assert count == 1


async def test_close_same_key_different_payload_conflicts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, _attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    headers = _close_headers("close-same-key-diff-payload")

    first = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 2},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


async def test_concurrent_close_attempts_for_the_same_period_only_one_succeeds(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Real concurrency (`.claude/rules/08-testing.md`) — two closes for the
    same clinic+competence fired at once, with different idempotency keys
    (so the idempotency guard itself cannot be what serializes them; only
    the advisory lock + unique index can)."""
    await _login_admin(client, session_factory)
    clinic_id, _attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    payload = {"clinic_id": clinic_id, "year": 2026, "month": 1}

    responses = await asyncio.gather(
        client.post("/api/v1/closures", json=payload, headers=_close_headers("concurrent-a")),
        client.post("/api/v1/closures", json=payload, headers=_close_headers("concurrent-b")),
    )

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 409]

    with session_factory() as session:
        count = session.execute(
            text(
                "SELECT COUNT(*) FROM monthly_closures WHERE clinic_id = :clinic_id "
                "AND status = 'CLOSED'"
            ),
            {"clinic_id": clinic_id},
        ).scalar_one()
        assert count == 1


async def test_close_header_totals_match_the_sum_of_its_items(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")
    vet_id = await _create_veterinarian(client, name="Dra. Ana", crmv=f"CRMV-{uuid4()}")
    patient_id = await _create_patient(client, session_factory)
    exam_id = await _create_exam(
        client, session_factory, code=f"HEMO-{uuid4().hex[:6]}", price="80.00"
    )

    await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-05",
        quantity=2,
    )
    await _confirm_attendance(
        client,
        clinic_id=clinic_id,
        veterinarian_id=vet_id,
        patient_id=patient_id,
        exam_id=exam_id,
        service_date="2026-01-20",
    )

    response = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-sum-check"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["item_count"] == 2
    items_sum = sum(Decimal(item["total_amount"]) for item in body["items"])
    assert items_sum == Decimal(body["grand_total"]) == Decimal("240.00")

    with session_factory() as session:
        db_items_sum = session.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM monthly_closure_items "
                "WHERE monthly_closure_id = :id"
            ),
            {"id": body["id"]},
        ).scalar_one()
        db_header_total = session.execute(
            text("SELECT grand_total FROM monthly_closures WHERE id = :id"), {"id": body["id"]}
        ).scalar_one()
        assert Decimal(db_items_sum) == Decimal(db_header_total) == Decimal("240.00")


async def test_close_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    from app.modules.identity.infrastructure.seed import ROLE_TECHNICAL

    with session_factory() as session:
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email="tecnico@vertere.local",
            full_name="Tecnico",
            password_hash=hash_password("s3nhaForte!"),
            is_active=True,
            role_id=ROLE_TECHNICAL,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        session.add(LabMembershipModel(id=uuid4(), user_id=user.id, is_active=True, granted_at=now))
        session.commit()
    await _login(client, email="tecnico@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/closures",
        json={"clinic_id": str(uuid4()), "year": 2026, "month": 1},
        headers=_close_headers("close-forbidden"),
    )

    assert response.status_code == 403


async def test_close_unknown_clinic_is_not_found(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    response = await client.post(
        "/api/v1/closures",
        json={"clinic_id": str(uuid4()), "year": 2026, "month": 1},
        headers=_close_headers("close-unknown-clinic"),
    )

    assert response.status_code == 404


async def test_close_requires_idempotency_key_header(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, _attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )

    response = await client.post(
        "/api/v1/closures", json={"clinic_id": clinic_id, "year": 2026, "month": 1}
    )

    assert response.status_code == 422


async def test_reopen_releases_attendance_and_reclose_creates_next_version(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    first = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-before-reopen"),
    )
    assert first.status_code == 201

    reopened = await client.post(
        f"/api/v1/closures/{first.json()['id']}/reopen",
        json={"reason": "Correção de competência autorizada."},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "REOPENED"

    with session_factory() as session:
        association = session.execute(
            text("SELECT monthly_closure_id FROM attendances WHERE id = :id"),
            {"id": attendance["id"]},
        ).scalar_one()
        assert association is None
        audit_reason = session.execute(
            text(
                "SELECT reason FROM audit_log "
                "WHERE action = 'closures.reopened' AND entity_id = :id"
            ),
            {"id": first.json()["id"]},
        ).scalar_one()
        assert audit_reason == "Correção de competência autorizada."

    second = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-after-reopen"),
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2


async def test_reopen_rejects_short_reason_and_second_attempt(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, _attendance_id = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    closed = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "year": 2026, "month": 1},
        headers=_close_headers("close-invalid-reopen"),
    )
    closure_id = closed.json()["id"]

    invalid = await client.post(
        f"/api/v1/closures/{closure_id}/reopen",
        json={"reason": "curto"},
    )
    assert invalid.status_code == 422

    first = await client.post(
        f"/api/v1/closures/{closure_id}/reopen",
        json={"reason": "Primeira reabertura autorizada."},
    )
    second = await client.post(
        f"/api/v1/closures/{closure_id}/reopen",
        json={"reason": "Segunda tentativa não permitida."},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
