"""Integração com PostgreSQL real (Testcontainers) — leitura/edição das
taxas de plantão configuráveis e a garantia de que um atendimento já
confirmado mantém seu `on_call_fee` snapshotado mesmo depois que a
configuração muda (`.claude/rules/12-attendance.md`: "atualização da tabela
de preço vigente nunca altera um snapshot já persistido" — mesmo princípio
aplicado à taxa de plantão, Fatia 2 do plano
`dentro-da-pasta-assets-enchanted-narwhal.md`).
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
from app.modules.identity.infrastructure.seed import (
    ROLE_FINANCE,
    ROLE_LAB_ADMIN,
    ROLE_RECEPTION,
    ROLE_TECHNICAL,
)
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
        # Restore the seeded fee amounts (migration 0031) so each test
        # starts from the same baseline instead of leaking edits made by
        # a previous test in this module.
        session.execute(
            text(
                "UPDATE on_call_fee_settings SET fee_amount = CASE service_level "
                "WHEN 'PLANTAO_NORMAL' THEN 100.00 WHEN 'PLANTAO_ESPECIAL' THEN 150.00 END, "
                "schedule_label = '', row_version = 1"
            )
        )
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


async def _login_as(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, role_id: UUID, email: str
) -> None:
    _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
    await _login(client, email=email, password="s3nhaForte!")


async def test_list_on_call_fee_settings_returns_seeded_tiers(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(
        client, session_factory, role_id=ROLE_RECEPTION, email="reception@vertere.local"
    )

    response = await client.get("/api/v1/on-call-fee-settings")

    assert response.status_code == 200
    items = {item["service_level"]: item for item in response.json()["items"]}
    assert items["PLANTAO_NORMAL"]["fee_amount"] == "100.00"
    assert items["PLANTAO_ESPECIAL"]["fee_amount"] == "150.00"
    assert items["PLANTAO_NORMAL"]["row_version"] == 1


async def test_list_on_call_fee_settings_without_pricing_read_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(
        client, session_factory, role_id=ROLE_TECHNICAL, email="technical@vertere.local"
    )

    response = await client.get("/api/v1/on-call-fee-settings")

    assert response.status_code == 403


async def test_update_on_call_fee_setting_with_pricing_manage_succeeds(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, role_id=ROLE_FINANCE, email="finance@vertere.local")

    response = await client.patch(
        "/api/v1/on-call-fee-settings/PLANTAO_NORMAL",
        json={
            "fee_amount": "130.00",
            "schedule_label": "Seg-Sáb - 19h às 07h",
            "expected_row_version": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fee_amount"] == "130.00"
    assert body["schedule_label"] == "Seg-Sáb - 19h às 07h"
    assert body["row_version"] == 2

    with session_factory() as session:
        row = session.execute(
            text("SELECT action FROM audit_log WHERE action = 'on_call_fee_settings.updated'")
        ).all()
        assert len(row) == 1


async def test_update_on_call_fee_setting_without_pricing_manage_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(
        client, session_factory, role_id=ROLE_RECEPTION, email="reception@vertere.local"
    )

    response = await client.patch(
        "/api/v1/on-call-fee-settings/PLANTAO_NORMAL",
        json={"fee_amount": "130.00", "schedule_label": "", "expected_row_version": 1},
    )

    assert response.status_code == 403


async def test_update_on_call_fee_setting_with_stale_row_version_is_conflict(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, role_id=ROLE_FINANCE, email="finance@vertere.local")

    first = await client.patch(
        "/api/v1/on-call-fee-settings/PLANTAO_ESPECIAL",
        json={"fee_amount": "160.00", "schedule_label": "", "expected_row_version": 1},
    )
    assert first.status_code == 200

    stale = await client.patch(
        "/api/v1/on-call-fee-settings/PLANTAO_ESPECIAL",
        json={"fee_amount": "170.00", "schedule_label": "", "expected_row_version": 1},
    )

    assert stale.status_code == 409


async def test_update_on_call_fee_setting_rejects_normal_service_level(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, role_id=ROLE_FINANCE, email="finance@vertere.local")

    response = await client.patch(
        "/api/v1/on-call-fee-settings/NORMAL",
        json={"fee_amount": "10.00", "schedule_label": "", "expected_row_version": 1},
    )

    # NORMAL is not part of the literal type accepted by the path — FastAPI
    # rejects it as a validation error before the use case's own check ever
    # runs (belt-and-suspenders: the use case still checks it, in case
    # anyone calls it directly outside the API).
    assert response.status_code == 422


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


async def _create_exam(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> str:
    category = await client.post("/api/v1/exam-categories", json={"name": "Hematológico"})
    assert category.status_code == 201
    species_id = _get_species_id(session_factory, name="Canino")
    response = await client.post(
        "/api/v1/exams",
        json={
            "code": "HEM01",
            "name": "Hemograma",
            "category_id": category.json()["id"],
            "price_base": "80.00",
            "description": None,
            "species_ids": [species_id],
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_confirmed_attendance_on_call_fee_unaffected_by_later_setting_change(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, role_id=ROLE_LAB_ADMIN, email="admin@vertere.local")

    clinic_id = await _create_clinic(client, "Clínica Teste")
    veterinarian_id = await _create_veterinarian(client, name="Dr. Teste", crmv="CRMV-SC 00001")
    patient_id = await _create_patient(client, session_factory)
    exam_id = await _create_exam(client, session_factory)

    draft = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
            "service_level": "PLANTAO_NORMAL",
            "service_date": "2026-02-10",
        },
    )
    assert draft.status_code == 201
    attendance_id = draft.json()["id"]

    confirm = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert confirm.status_code == 200
    assert confirm.json()["on_call_fee"] == "100.00"

    updated = await client.patch(
        "/api/v1/on-call-fee-settings/PLANTAO_NORMAL",
        json={"fee_amount": "999.00", "schedule_label": "", "expected_row_version": 1},
    )
    assert updated.status_code == 200

    reread = await client.get(f"/api/v1/attendances/{attendance_id}")
    assert reread.status_code == 200
    assert reread.json()["on_call_fee"] == "100.00"
