"""Integração com PostgreSQL real (Testcontainers) — leitura/edição das
taxas de plantão configuráveis e a garantia de que um atendimento já
confirmado mantém seu `on_call_fee` snapshotado mesmo depois que a
configuração muda (`.claude/rules/12-attendance.md`: "atualização da tabela
de preço vigente nunca altera um snapshot já persistido" — mesmo princípio
aplicado à taxa de plantão, Fatia 2 do plano
`dentro-da-pasta-assets-enchanted-narwhal.md`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import (
    ROLE_FINANCE,
    ROLE_LAB_ADMIN,
    ROLE_RECEPTION,
    ROLE_TECHNICAL,
)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
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
        # Restore the seeded fee amounts (migration 0031) so each test
        # starts from the same baseline instead of leaking edits made by
        # a previous test in this module.
        session.execute(
            text(
                "UPDATE on_call_fee_settings SET fee_amount = CASE service_level "
                "WHEN 'PLANTAO_NORMAL' THEN 100.00 WHEN 'PLANTAO_ESPECIAL' THEN 150.00 END, "
                "schedule_label = '', weekdays = '{}', start_time = NULL, end_time = NULL, "
                "row_version = 1"
            )
        )
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


async def _login_as(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, role_id: UUID, email: str
) -> None:
    _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
    await _login(client, email=email, password="s3nhaForte!")


async def test_on_call_fee_settings_are_permission_gated_audited_versioned_and_tier_restricted(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    url = "/api/v1/on-call-fee-settings"
    await _login_as(
        client, session_factory, role_id=ROLE_TECHNICAL, email="technical@vertere.local"
    )
    assert (await client.get(url)).status_code == 403

    await _login_as(
        client, session_factory, role_id=ROLE_RECEPTION, email="reception@vertere.local"
    )
    listed = await client.get(url)
    assert listed.status_code == 200
    items = {item["service_level"]: item for item in listed.json()["items"]}
    assert items["PLANTAO_NORMAL"]["fee_amount"] == "100.00"
    assert items["PLANTAO_ESPECIAL"]["fee_amount"] == "150.00"
    assert items["PLANTAO_NORMAL"]["row_version"] == 1
    read_only = await client.patch(
        f"{url}/PLANTAO_NORMAL",
        json={
            "fee_amount": "130.00",
            "reason": "Reajuste",
            "expected_row_version": 1,
        },
    )
    assert read_only.status_code == 403

    await _login_as(client, session_factory, role_id=ROLE_FINANCE, email="finance@vertere.local")
    updated = await client.patch(
        f"{url}/PLANTAO_NORMAL",
        json={
            "fee_amount": "130.00",
            "weekdays": [0, 1, 2, 3, 4, 5],
            "start_time": "19:00",
            "end_time": "07:00",
            "reason": "Reajuste",
            "expected_row_version": 1,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert (body["fee_amount"], body["schedule_label"], body["row_version"]) == (
        "130.00",
        "Seg-Sáb · 19h às 07h",
        2,
    )
    with session_factory() as session:
        audited = session.execute(
            text("SELECT action FROM audit_log WHERE action = 'on_call_fee_settings.updated'")
        ).all()
    assert len(audited) == 1

    first = await client.patch(
        f"{url}/PLANTAO_ESPECIAL",
        json={
            "fee_amount": "160.00",
            "reason": "Reajuste",
            "expected_row_version": 1,
        },
    )
    assert first.status_code == 200
    stale = await client.patch(
        f"{url}/PLANTAO_ESPECIAL",
        json={
            "fee_amount": "170.00",
            "reason": "Reajuste",
            "expected_row_version": 1,
        },
    )
    assert stale.status_code == 409

    # NORMAL não faz parte do tipo literal do path: 422 antes do caso de uso
    # (que ainda checa, caso seja chamado fora da API).
    normal = await client.patch(
        f"{url}/NORMAL",
        json={
            "fee_amount": "10.00",
            "reason": "Reajuste",
            "expected_row_version": 1,
        },
    )
    assert normal.status_code == 422


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


async def _create_exam(client: httpx.AsyncClient, session_factory: sessionmaker[Session]) -> str:
    category = await client.post("/api/v1/exam-categories", json={"name": "Hematológico"})
    assert category.status_code == 201
    species_id = _get_species_id(session_factory, name="Canino")
    response = await client.post(
        "/api/v1/exams",
        json={
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
        json={
            "fee_amount": "999.00",
            "reason": "Reajuste",
            "expected_row_version": 1,
        },
    )
    assert updated.status_code == 200

    reread = await client.get(f"/api/v1/attendances/{attendance_id}")
    assert reread.status_code == 200
    assert reread.json()["on_call_fee"] == "100.00"


async def test_fee_schedule_fields_are_validated_stored_and_audited(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, role_id=ROLE_FINANCE, email="finance@vertere.local")
    url = "/api/v1/on-call-fee-settings/PLANTAO_ESPECIAL"
    base = {"fee_amount": "150.00", "reason": "Ajuste de horário", "expected_row_version": 1}

    for bad in (
        {"weekdays": [7]},
        {"weekdays": [1, 1]},
        {"start_time": "18:00"},
        {"start_time": "18:00", "end_time": "18:00"},
        {"schedule_label": "texto livre"},
    ):
        response = await client.patch(url, json={**base, **bad})
        assert response.status_code == 422, bad

    ok = await client.patch(
        url,
        json={**base, "weekdays": [4, 5, 6], "start_time": "18:00", "end_time": "07:00"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["weekdays"] == [4, 5, 6]
    assert (body["start_time"], body["end_time"]) == ("18:00:00", "07:00:00")
    assert body["schedule_label"] == "Sex-Dom · 18h às 07h"

    # A urgência é só um valor fixo: dias e horário não existem para ela.
    urgency_version = (await client.get("/api/v1/urgency-fee-setting")).json()["row_version"]
    for extra in ({"weekdays": [0, 1]}, {"start_time": "08:00", "end_time": "12:00"}):
        rejected = await client.patch(
            "/api/v1/urgency-fee-setting",
            json={
                "fee_amount": "30.00",
                "reason": "Horário",
                "expected_row_version": urgency_version,
                **extra,
            },
        )
        assert rejected.status_code == 422, extra
    urgency = await client.patch(
        "/api/v1/urgency-fee-setting",
        json={"fee_amount": "30.00", "reason": "Valor", "expected_row_version": urgency_version},
    )
    assert urgency.status_code == 200
    assert set(urgency.json()) == {"id", "fee_amount", "updated_at", "row_version"}

    with session_factory() as session:
        states = session.execute(
            text(
                "SELECT before_state->'weekdays', after_state->'weekdays', reason FROM audit_log "
                "WHERE action = 'on_call_fee_settings.updated'"
            )
        ).all()
        session.execute(text("UPDATE urgency_fee_settings SET fee_amount = 0, row_version = 1"))
        session.commit()
    assert [tuple(row) for row in states] == [([], [4, 5, 6], "Ajuste de horário")]
