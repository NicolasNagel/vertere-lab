"""Integração com PostgreSQL real (Testcontainers) — GET /closures/preview
ponta a ponta via HTTPX/ASGI.

Esta fatia cobre só a prévia (Incremento 4.1) — read-only, sem persistência
(`.claude/rules/13-monthly-closure.md`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_FINANCE, ROLE_LAB_ADMIN, ROLE_RECEPTION

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


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


async def _create_patient(
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    *,
    clinic_id: str | None = None,
) -> str:
    species_id = _get_species_id(session_factory, name="Canino")
    if clinic_id is None:
        with session_factory() as session:
            clinic_id = str(session.execute(text("SELECT id FROM clinics LIMIT 1")).scalar_one())
    response = await client.post(
        "/api/v1/patients",
        json={
            "clinic_id": clinic_id,
            "name": "Rex",
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": "Maria Souza",
        },
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


async def test_preview_splits_eligible_and_blocked_items_isolates_clinics_and_persists_nothing(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_a = await _create_clinic(client, "Schweitzer")
    clinic_b = await _create_clinic(client, "VetCenter")
    clinic_empty = await _create_clinic(client, "Sem Atendimentos")
    vet_id = await _create_veterinarian(client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567")
    patient_a = await _create_patient(client, session_factory, clinic_id=clinic_a)
    patient_b = await _create_patient(client, session_factory, clinic_id=clinic_b)
    exam_id = await _create_exam(client, session_factory, code="HEMO-001", price="100.00")
    january = {"period_start": "2026-01-01", "period_end": "2026-01-31"}

    async def confirm(
        clinic_id: str, patient_id: str, service_date: str, quantity: int = 1
    ) -> dict[str, object]:
        return await _confirm_attendance(
            client,
            clinic_id=clinic_id,
            veterinarian_id=vet_id,
            patient_id=patient_id,
            exam_id=exam_id,
            service_date=service_date,
            quantity=quantity,
        )

    eligible_1 = await confirm(clinic_a, patient_a, "2026-01-05", quantity=2)
    eligible_2 = await confirm(clinic_a, patient_a, "2026-01-20")
    await confirm(clinic_a, patient_a, "2026-02-01")  # fora da competência
    blocked = await confirm(clinic_a, patient_a, "2026-01-10")
    cancelled = await confirm(clinic_b, patient_b, "2026-01-05")
    with session_factory() as session:
        # Item cancelado dentro da competência aparece como bloqueado.
        session.execute(
            text("UPDATE attendance_exams SET status = 'CANCELLED' WHERE attendance_id = :id"),
            {"id": blocked["id"]},
        )
        session.execute(
            text("UPDATE attendances SET status = 'CANCELLED' WHERE id = :id"),
            {"id": cancelled["id"]},
        )
        session.commit()

    def table_counts() -> dict[str, int]:
        with session_factory() as session:
            return {
                table: session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                for table in ("attendances", "attendance_exams", "audit_log")
            }

    before = table_counts()
    response = await client.get(
        "/api/v1/closures/preview", params={"clinic_id": clinic_a, **january}
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["competence_year"], body["competence_month"]) == (2026, 1)
    assert (body["period_start"], body["period_end"]) == ("2026-01-01", "2026-01-31")
    assert (body["attendance_count"], body["cancelled_attendance_count"]) == (3, 0)
    assert body["item_count"] == 2
    assert Decimal(body["subtotal"]) == Decimal("300.00")
    assert Decimal(body["grand_total"]) == Decimal("300.00")
    assert {item["attendance_id"] for item in body["eligible_items"]} == {
        eligible_1["id"],
        eligible_2["id"],
    }
    assert all(item["service_level"] == "NORMAL" for item in body["eligible_items"])
    assert all(item["exam_category"] == "Cat HEMO-001" for item in body["eligible_items"])
    blocked_entry = next(i for i in body["blocked_items"] if i["attendance_id"] == blocked["id"])
    assert blocked_entry["reason"]
    assert table_counts() == before, "a prévia é read-only"

    # Atendimento cancelado fica fora dos itens elegíveis e é contado à parte.
    cancelled_preview = (
        await client.get("/api/v1/closures/preview", params={"clinic_id": clinic_b, **january})
    ).json()
    assert (
        cancelled_preview["attendance_count"],
        cancelled_preview["cancelled_attendance_count"],
    ) == (1, 1)
    assert cancelled_preview["item_count"] == 0
    assert Decimal(cancelled_preview["grand_total"]) == Decimal("0")
    assert len(cancelled_preview["blocked_items"]) == 1

    # Outra clínica sem atendimentos não enxerga os das demais.
    empty = (
        await client.get("/api/v1/closures/preview", params={"clinic_id": clinic_empty, **january})
    ).json()
    assert (empty["attendance_count"], empty["item_count"]) == (0, 0)


async def test_preview_is_authenticated_permission_gated_and_validates_input(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    january = {"period_start": "2026-01-01", "period_end": "2026-01-31"}
    unauthenticated = await client.get(
        "/api/v1/closures/preview", params={"clinic_id": str(uuid4()), **january}
    )
    assert unauthenticated.status_code == 401

    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    unknown = await client.get(
        "/api/v1/closures/preview", params={"clinic_id": str(uuid4()), **january}
    )
    assert unknown.status_code == 404
    reversed_period = await client.get(
        "/api/v1/closures/preview",
        params={"clinic_id": clinic_id, "period_start": "2026-01-31", "period_end": "2026-01-01"},
    )
    assert reversed_period.status_code == 422

    for email, role_id, expected in (
        ("reception@vertere.local", ROLE_RECEPTION, 403),
        ("finance@vertere.local", ROLE_FINANCE, 200),
    ):
        await client.post("/api/v1/auth/logout")
        _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
        await _login(client, email=email, password="s3nhaForte!")
        response = await client.get(
            "/api/v1/closures/preview", params={"clinic_id": clinic_id, **january}
        )
        assert response.status_code == expected, email
