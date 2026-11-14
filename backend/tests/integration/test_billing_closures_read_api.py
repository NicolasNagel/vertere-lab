"""Integração com PostgreSQL real (Testcontainers) — `GET /closures`,
`GET /closures/{id}` e `GET /closures/{id}/export` ponta a ponta via
HTTPX/ASGI (Fatia C do Incremento 4.2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_TECHNICAL

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM outbox_events"))
        session.execute(text("DELETE FROM idempotency_keys"))
        session.execute(text("DELETE FROM monthly_closure_items"))
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


async def _login(client: httpx.AsyncClient, *, email: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": password, "remember_me": False},
    )
    assert response.status_code == 200


async def _login_admin(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> None:
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
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")


async def _login_technical(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
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


async def _create_patient(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, clinic_id: str
) -> str:
    species_id = _get_species_id(session_factory)
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
    species_id = _get_species_id(session_factory)
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


async def _close_clinic_period(
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    *,
    service_date: str,
    period_start: str,
    period_end: str,
    idempotency_key: str,
) -> dict[str, object]:
    clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")
    vet_id = await _create_veterinarian(client, name="Dra. Ana", crmv=f"CRMV-{uuid4()}")
    patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
    exam_id = await _create_exam(
        client, session_factory, code=f"HEMO-{uuid4().hex[:6]}", price="100.00"
    )

    draft_response = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": clinic_id,
            "veterinarian_id": vet_id,
            "patient_id": patient_id,
            "service_date": service_date,
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

    close_response = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "period_start": period_start, "period_end": period_end},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert close_response.status_code == 201
    body: dict[str, object] = close_response.json()
    return body


async def test_closure_reads_are_permission_gated_and_return_snapshot_list_and_csv(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_technical(client, session_factory)
    assert (await client.get(f"/api/v1/closures/{uuid4()}")).status_code == 403

    await _login_admin(client, session_factory)
    assert (await client.get(f"/api/v1/closures/{uuid4()}")).status_code == 404
    assert (await client.get(f"/api/v1/closures/{uuid4()}/export")).status_code == 404

    closure_a = await _close_clinic_period(
        client,
        session_factory,
        service_date="2026-04-10",
        period_start="2026-04-01",
        period_end="2026-04-30",
        idempotency_key="list-closure-a",
    )
    closure_b = await _close_clinic_period(
        client,
        session_factory,
        service_date="2026-04-11",
        period_start="2026-04-01",
        period_end="2026-04-30",
        idempotency_key="list-closure-b",
    )

    # Detalhe devolve o snapshot completo.
    detail = await client.get(f"/api/v1/closures/{closure_a['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert (body["id"], body["status"]) == (closure_a["id"], "CLOSED")
    assert len(body["items"]) == 1
    assert Decimal(body["grand_total"]) == Decimal("100.00")

    # Lista é paginada, resumida (sem `items`) e filtrável por clínica.
    listed = await client.get("/api/v1/closures", params={"page": 1, "page_size": 20})
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert {item["id"] for item in listed.json()["items"]} == {closure_a["id"], closure_b["id"]}
    assert "items" not in listed.json()["items"][0]
    scoped = await client.get("/api/v1/closures", params={"clinic_id": str(closure_a["clinic_id"])})
    assert scoped.status_code == 200
    assert scoped.json()["total"] == 1
    assert scoped.json()["items"][0]["id"] == closure_a["id"]

    # Exportação CSV espelha o snapshot.
    export = await client.get(f"/api/v1/closures/{closure_b['id']}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "attachment" in export.headers["content-disposition"]
    lines = export.text.strip("\r\n").split("\r\n")
    assert lines[0] == "protocolo,paciente,exame,preco_base,quantidade,desconto,adicional,total"
    assert len(lines) == 2
    item = closure_b["items"][0]  # type: ignore[index]
    assert lines[1] == (
        f"{item['protocol_number']},{item['patient_name']},{item['exam_name']},"
        f"{item['price_base']},{item['quantity']},{item['discount_amount']},"
        f"{item['surcharge_amount']},{item['total_amount']}"
    )
