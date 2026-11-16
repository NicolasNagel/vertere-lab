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

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.billing.domain.entities import ClosureStatus, MonthlyClosure, MonthlyClosureItem
from app.modules.billing.infrastructure.repositories import SqlAlchemyMonthlyClosureRepository
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


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
        session.execute(text("DELETE FROM exam_panel_items"))
        session.execute(text("DELETE FROM exams"))
        session.execute(text("DELETE FROM exam_categories"))
        session.execute(text("DELETE FROM veterinarian_clinics"))
        session.execute(text("DELETE FROM patients"))
        session.execute(text("DELETE FROM veterinarians"))
        session.execute(text("DELETE FROM clinics"))
        session.execute(text("DELETE FROM users"))
        session.commit()


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
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    *,
    clinic_id: str | None = None,
) -> dict[str, object]:
    """Real DRAFT -> CONFIRMED flow via the API — this fatia has no closure
    endpoint yet, but the source item snapshotted must be a real
    `attendance_exams` row, not a hand-crafted UUID that would violate the
    FK."""
    if clinic_id is None:
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


async def _persist_closure(
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    *,
    clinic_id: str | None = None,
    period_start: date = date(2026, 1, 1),
    period_end: date = date(2026, 1, 31),
) -> MonthlyClosure:
    """Confirmed attendance via the API, closure inserted by the repository."""
    source = await _confirmed_attendance_exam(client, session_factory, clinic_id=clinic_id)
    closure = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=source["attendance"],  # type: ignore[arg-type]
        item=source["item"],  # type: ignore[arg-type]
        period_start=period_start,
        period_end=period_end,
    )
    with session_factory() as session:
        SqlAlchemyMonthlyClosureRepository(session).add(closure)
        session.commit()
    return closure


async def test_repository_round_trips_a_closure_links_the_attendance_and_rejects_a_duplicate(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login(client, session_factory)
    source = await _confirmed_attendance_exam(client, session_factory)
    closure = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=source["attendance"],  # type: ignore[arg-type]
        item=source["item"],  # type: ignore[arg-type]
    )
    attendance_id = str(source["attendance"]["id"])  # type: ignore[index]

    with session_factory() as session:
        repo = SqlAlchemyMonthlyClosureRepository(session)
        repo.add(closure)
        session.flush()
        # A FK de `attendances.monthly_closure_id` aceita o vínculo.
        session.execute(
            text("UPDATE attendances SET monthly_closure_id = :closure_id WHERE id = :id"),
            {"closure_id": str(closure.id), "id": attendance_id},
        )
        session.commit()

    with session_factory() as session:
        repo = SqlAlchemyMonthlyClosureRepository(session)
        loaded = repo.get_by_id(closure.id)
        assert loaded is not None
        assert (loaded.status, loaded.item_count) == (ClosureStatus.CLOSED, 1)
        assert loaded.grand_total == Decimal("100.00")
        assert [item.exam_name for item in loaded.items] == ["Hemograma"]

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

        linked = session.execute(
            text("SELECT monthly_closure_id FROM attendances WHERE id = :id"), {"id": attendance_id}
        ).one()
        assert str(linked[0]) == str(closure.id)

    # O banco rejeita um segundo fechamento para a mesma clínica e período.
    duplicate_source = await _confirmed_attendance_exam(
        client, session_factory, clinic_id=str(source["clinic_id"])
    )
    duplicate = _closure_from_confirmed(
        clinic_id=str(source["clinic_id"]),
        attendance=duplicate_source["attendance"],  # type: ignore[arg-type]
        item=duplicate_source["item"],  # type: ignore[arg-type]
    )
    with session_factory() as session, pytest.raises(IntegrityError):
        SqlAlchemyMonthlyClosureRepository(session).add(duplicate)
        session.commit()


async def test_database_rejects_partially_overlapping_periods_but_accepts_back_to_back_ones(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """The invariant is an overlap check (migration 0037's EXCLUDE), not an
    exact year+month match: 1-20 vs. 15-31 conflict, 1-15 then 16-31 coexist."""
    await _login(client, session_factory)
    first = await _persist_closure(
        client, session_factory, period_start=date(2026, 1, 1), period_end=date(2026, 1, 15)
    )

    overlapping_source = await _confirmed_attendance_exam(
        client, session_factory, clinic_id=str(first.clinic_id)
    )
    overlapping = _closure_from_confirmed(
        clinic_id=str(first.clinic_id),
        attendance=overlapping_source["attendance"],  # type: ignore[arg-type]
        item=overlapping_source["item"],  # type: ignore[arg-type]
        period_start=date(2026, 1, 10),
        period_end=date(2026, 1, 31),
    )
    with session_factory() as session, pytest.raises(IntegrityError):
        SqlAlchemyMonthlyClosureRepository(session).add(overlapping)
        session.commit()

    second = await _persist_closure(
        client,
        session_factory,
        clinic_id=str(first.clinic_id),
        period_start=date(2026, 1, 16),
        period_end=date(2026, 1, 31),
    )
    with session_factory() as session:
        page, total = SqlAlchemyMonthlyClosureRepository(session).list_page(
            clinic_id=first.clinic_id, page=1, page_size=20
        )
        assert total == 2
        assert {item.id for item in page} == {first.id, second.id}
