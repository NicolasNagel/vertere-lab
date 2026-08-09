"""Integração com PostgreSQL real (Testcontainers) para a fundação de
persistência do Incremento 4.2 — `MonthlyClosure`/`MonthlyClosureItem` e a
FK que faltava em `attendances.monthly_closure_id`.

Sem caso de uso/endpoint ainda (isso é a próxima fatia) — os atendimentos
confirmados usados como fonte do snapshot vêm da API real (mesmo padrão de
`test_billing_api.py`), mas o fechamento em si é criado direto pelo
repositório, para validar a fundação isoladamente antes de existir
`POST /closures`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.modules.billing.domain.entities import ClosureStatus, MonthlyClosure, MonthlyClosureItem
from app.modules.billing.infrastructure.repositories import SqlAlchemyMonthlyClosureRepository
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


def _create_user(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email="admin@vertere.local",
            full_name="Admin",
            password_hash=hash_password("s3nhaForte!"),
            is_active=True,
            role_id=ROLE_LAB_ADMIN,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        session.add(LabMembershipModel(id=uuid4(), user_id=user.id, is_active=True, granted_at=now))
        session.commit()


async def _login(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> None:
    _create_user(session_factory)
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": "admin@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )
    assert response.status_code == 200


def _get_species_id(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as session:
        row = session.execute(
            text("SELECT id FROM species WHERE name = :name"), {"name": "Canino"}
        ).one()
        return str(row[0])


async def _confirmed_attendance_exam(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> dict[str, object]:
    """Real DRAFT -> CONFIRMED flow via the API — this fatia has no closure
    endpoint yet, but the source item snapshotted must be a real
    `attendance_exams` row, not a hand-crafted UUID that would violate the
    FK."""
    clinic_response = await client.post("/api/v1/clinics", json={"name": f"Clinica {uuid4()}"})
    assert clinic_response.status_code == 201
    clinic_id = clinic_response.json()["id"]

    vet_response = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": "Dra. Ana",
            "crmv": f"CRMV-{uuid4()}",
            "is_autonomous": True,
            "clinic_ids": [],
        },
    )
    assert vet_response.status_code == 201
    vet_id = vet_response.json()["id"]

    species_id = _get_species_id(session_factory)
    patient_response = await client.post(
        "/api/v1/patients",
        json={
            "clinic_id": clinic_id,
            "name": "Rex",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
    )
    assert patient_response.status_code == 201
    patient_id = patient_response.json()["id"]

    category_response = await client.post(
        "/api/v1/exam-categories", json={"name": f"Cat {uuid4()}"}
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]
    exam_response = await client.post(
        "/api/v1/exams",
        json={
            "code": f"HEMO-{uuid4().hex[:6]}",
            "name": "Hemograma",
            "category_id": category_id,
            "price_base": "100.00",
            "species_ids": [species_id],
        },
    )
    assert exam_response.status_code == 201
    exam_id = exam_response.json()["id"]

    draft_response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": vet_id,
            "patient_id": patient_id,
            "service_date": "2026-01-10",
        },
    )
    assert draft_response.status_code == 201
    attendance_id = draft_response.json()["id"]

    confirm_response = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={"items": [{"exam_id": exam_id, "quantity": 1}]},
        headers={"Idempotency-Key": f"confirm-{attendance_id}"},
    )
    assert confirm_response.status_code == 200
    body = confirm_response.json()
    return {"clinic_id": clinic_id, "attendance": body, "item": body["items"][0]}


def _closure_from_confirmed(
    *,
    clinic_id: str,
    attendance: dict[str, object],
    item: dict[str, object],
    period_start: date = date(2026, 1, 1),
    period_end: date = date(2026, 1, 31),
) -> MonthlyClosure:
    closure_id = uuid4()
    closure_item = MonthlyClosureItem(
        id=uuid4(),
        monthly_closure_id=closure_id,
        attendance_id=UUID(str(attendance["id"])),
        attendance_exam_id=UUID(str(item["id"])),
        protocol_number=str(attendance["protocol_number"]),
        patient_name="Rex",
        exam_name=str(item["exam_name"]),
        price_base=Decimal(str(item["price_base"])),
        quantity=int(item["quantity"]),  # type: ignore[call-overload]
        discount_amount=Decimal(str(item["discount_amount"])),
        surcharge_amount=Decimal(str(item["surcharge_amount"])),
        total_amount=Decimal(str(item["total_amount"])),
    )
    return MonthlyClosure(
        id=closure_id,
        clinic_id=UUID(clinic_id),
        competence_year=period_start.year,
        competence_month=period_start.month,
        period_start=period_start,
        period_end=period_end,
        status=ClosureStatus.CLOSED,
        item_count=1,
        subtotal=closure_item.price_base * closure_item.quantity,
        discount_total=closure_item.discount_amount,
        surcharge_total=closure_item.surcharge_amount,
        grand_total=closure_item.total_amount,
        generated_by=None,
        closed_by=None,
        generated_at=datetime.now(UTC),
        closed_at=datetime.now(UTC),
        items=[closure_item],
    )


async def test_repository_round_trips_a_closure_with_its_items(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login(client, session_factory)
    source = await _confirmed_attendance_exam(client, session_factory)
    closure = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=source["attendance"],  # type: ignore[arg-type]
        item=source["item"],  # type: ignore[arg-type]
    )

    with session_factory() as session:
        repo = SqlAlchemyMonthlyClosureRepository(session)
        repo.add(closure)
        session.commit()

    with session_factory() as session:
        repo = SqlAlchemyMonthlyClosureRepository(session)
        loaded = repo.get_by_id(closure.id)
        assert loaded is not None
        assert loaded.status == ClosureStatus.CLOSED
        assert loaded.item_count == 1
        assert loaded.grand_total == Decimal("100.00")
        assert len(loaded.items) == 1
        assert loaded.items[0].exam_name == "Hemograma"

        active = repo.get_active_for_clinic_and_period(
            clinic_id=closure.clinic_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        assert active is not None
        assert active.id == closure.id

        page, total = repo.list_page(clinic_id=closure.clinic_id, page=1, page_size=20)
        assert total == 1
        assert page[0].id == closure.id


async def test_database_rejects_a_second_closed_closure_for_the_same_clinic_and_period(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login(client, session_factory)
    source = await _confirmed_attendance_exam(client, session_factory)
    first = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=source["attendance"],  # type: ignore[arg-type]
        item=source["item"],  # type: ignore[arg-type]
    )

    with session_factory() as session:
        SqlAlchemyMonthlyClosureRepository(session).add(first)
        session.commit()

    second_source = await _confirmed_attendance_exam(client, session_factory)
    second = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=second_source["attendance"],  # type: ignore[arg-type]
        item=second_source["item"],  # type: ignore[arg-type]
    )

    with session_factory() as session, pytest.raises(IntegrityError):
        SqlAlchemyMonthlyClosureRepository(session).add(second)
        session.commit()


async def test_database_rejects_two_free_periods_that_partially_overlap(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """The uniqueness invariant is now an overlap check, not an exact
    year+month match — two quinzena-shaped periods that partially overlap
    (1-20 vs. 15-31) must still conflict (migration 0037's EXCLUDE
    constraint), even though neither is a full calendar month."""
    await _login(client, session_factory)
    source = await _confirmed_attendance_exam(client, session_factory)
    first = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=source["attendance"],  # type: ignore[arg-type]
        item=source["item"],  # type: ignore[arg-type]
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 20),
    )

    with session_factory() as session:
        SqlAlchemyMonthlyClosureRepository(session).add(first)
        session.commit()

    second_source = await _confirmed_attendance_exam(client, session_factory)
    second = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=second_source["attendance"],  # type: ignore[arg-type]
        item=second_source["item"],  # type: ignore[arg-type]
        period_start=date(2026, 1, 15),
        period_end=date(2026, 1, 31),
    )

    with session_factory() as session, pytest.raises(IntegrityError):
        SqlAlchemyMonthlyClosureRepository(session).add(second)
        session.commit()


async def test_database_accepts_two_non_overlapping_biweekly_periods_for_the_same_clinic(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Two real quinzenas of the same clinic, back to back with no overlap,
    must both close successfully — this is the whole point of the feature."""
    await _login(client, session_factory)
    source = await _confirmed_attendance_exam(client, session_factory)
    first_half = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=source["attendance"],  # type: ignore[arg-type]
        item=source["item"],  # type: ignore[arg-type]
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 15),
    )

    with session_factory() as session:
        SqlAlchemyMonthlyClosureRepository(session).add(first_half)
        session.commit()

    second_source = await _confirmed_attendance_exam(client, session_factory)
    second_half = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=second_source["attendance"],  # type: ignore[arg-type]
        item=second_source["item"],  # type: ignore[arg-type]
        period_start=date(2026, 1, 16),
        period_end=date(2026, 1, 31),
    )

    with session_factory() as session:
        SqlAlchemyMonthlyClosureRepository(session).add(second_half)
        session.commit()

    with session_factory() as session:
        page, total = SqlAlchemyMonthlyClosureRepository(session).list_page(
            clinic_id=UUID(str(source["clinic_id"])), page=1, page_size=20
        )
        assert total == 2
        assert {item.id for item in page} == {first_half.id, second_half.id}


async def test_setting_attendance_monthly_closure_id_links_it_to_the_closure(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login(client, session_factory)
    source = await _confirmed_attendance_exam(client, session_factory)
    closure = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=source["attendance"],  # type: ignore[arg-type]
        item=source["item"],  # type: ignore[arg-type]
    )

    with session_factory() as session:
        SqlAlchemyMonthlyClosureRepository(session).add(closure)
        session.flush()
        session.execute(
            text(
                "UPDATE attendances SET monthly_closure_id = :closure_id WHERE id = :attendance_id"
            ),
            {"closure_id": str(closure.id), "attendance_id": str(source["attendance"]["id"])},  # type: ignore[index]
        )
        session.commit()

    with session_factory() as session:
        row = session.execute(
            text("SELECT monthly_closure_id FROM attendances WHERE id = :id"),
            {"id": str(source["attendance"]["id"])},  # type: ignore[index]
        ).one()
        assert str(row[0]) == str(closure.id)
