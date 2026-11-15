"""Integração com PostgreSQL real (Testcontainers) — criação de rascunho de
atendimento, confirmação com protocolo/itens financeiros, listagem, leitura
e autorização, ponta a ponta via HTTPX/ASGI.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import Row, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import (
    LabMembershipModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    UserModel,
)
from app.modules.identity.infrastructure.seed import ROLE_FINANCE, ROLE_LAB_ADMIN, ROLE_RECEPTION

pytestmark = pytest.mark.integration


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


async def _create_patient(
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    *,
    clinic_id: str | None = None,
) -> str:
    species_id = _get_species_id(session_factory, name="Canino")
    with session_factory() as session:
        clinic = session.execute(
            text("SELECT id FROM clinics ORDER BY created_at DESC LIMIT 1")
        ).scalar_one_or_none()
    if clinic_id is not None:
        pass
    elif clinic is None:
        clinic_response = await client.post(
            "/api/v1/clinics", json={"name": f"Clínica Paciente {uuid4()}"}
        )
        assert clinic_response.status_code == 201
        clinic_id = str(clinic_response.json()["id"])
    else:
        clinic_id = str(clinic)
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


async def _switch_user(
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session],
    *,
    email: str,
    role_id: UUID,
) -> None:
    """Logs the current session out and signs in as a freshly created user of `role_id`."""
    await client.post("/api/v1/auth/logout")
    _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
    await _login(client, email=email, password="s3nhaForte!")


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
) -> str:
    response = await client.post(
        "/api/v1/exams",
        json={
            "name": "Hemograma",
            "category_id": category_id,
            "price_base": price_base,
            "species_ids": species_ids,
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
) -> tuple[str, str]:
    """Returns (attendance_id, exam_id) for a DRAFT ready to confirm."""
    unique = uuid4().hex[:8]
    clinic_id = await _create_clinic(client, f"Schweitzer {unique}")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv=f"CRMV-SC {unique}"
    )
    patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
    species_id = _get_species_id(session_factory, name="Canino")
    category_id = await _create_exam_category(client, f"Hematologia {unique}")
    exam_id = await _create_exam(
        client,
        code=f"HEMO-{unique}",
        category_id=category_id,
        price_base="100.00",
        species_ids=[species_id],
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


def _items(exam_id: str, quantity: int = 1) -> dict[str, list[dict[str, object]]]:
    return {"items": [{"exam_id": exam_id, "quantity": quantity}]}


def _audit_row(session_factory: sessionmaker[Session], action: str) -> Row[Any]:
    with session_factory() as session:
        return session.execute(
            text(
                "SELECT action, entity_id, reason FROM audit_log "
                "WHERE action = :action ORDER BY occurred_at DESC LIMIT 1"
            ),
            {"action": action},
        ).one()


async def test_draft_creation_validates_every_reference_and_lists_with_filters(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    # Sem login, a listagem e a leitura exigem autenticação.
    assert (await client.get("/api/v1/attendances")).status_code == 401

    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    other_clinic_id = await _create_clinic(client, "VetCenter")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567"
    )
    linked_elsewhere_id = await _create_veterinarian(
        client,
        name="Eberton Henrique",
        crmv="CRMV-SC 08915",
        is_autonomous=False,
        clinic_ids=[other_clinic_id],
    )
    patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
    other_patient_id = await _create_patient(client, session_factory, clinic_id=other_clinic_id)
    inactive_patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
    assert (
        await client.post(f"/api/v1/patients/{inactive_patient_id}/deactivate")
    ).status_code == 200

    def draft(**overrides: object) -> dict[str, object]:
        return {
            "clinic_id": clinic_id,
            "veterinarian_id": veterinarian_id,
            "patient_id": patient_id,
            **overrides,
        }

    created = await client.post(
        "/api/v1/attendances/drafts",
        json=draft(service_date="2026-01-10", notes="Consulta de rotina"),
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["status"], body["clinic_id"], body["notes"]) == (
        "DRAFT",
        clinic_id,
        "Consulta de rotina",
    )
    assert (body["veterinarian_id"], body["patient_id"]) == (veterinarian_id, patient_id)
    fetched = await client.get(f"/api/v1/attendances/{body['id']}")
    assert (fetched.status_code, fetched.json()["status"]) == (200, "DRAFT")
    assert (await client.get(f"/api/v1/attendances/{uuid4()}")).status_code == 404

    # Todo id é revalidado (.claude/rules/12-attendance.md, ADR-003).
    rejected = {
        "unknown clinic": (draft(clinic_id=str(uuid4())), 404),
        # Veterinário não autônomo sem vínculo com a clínica escolhida não pode originar ali.
        "vet not linked to the clinic": (draft(veterinarian_id=linked_elsewhere_id), 422),
        "inactive patient": (draft(patient_id=inactive_patient_id), 422),
    }
    for label, (payload, expected_status) in rejected.items():
        response = await client.post("/api/v1/attendances/drafts", json=payload)
        assert response.status_code == expected_status, label

    await client.post(
        "/api/v1/attendances/drafts",
        json=draft(
            clinic_id=other_clinic_id, patient_id=other_patient_id, service_date="2026-02-10"
        ),
    )

    by_clinic = await client.get("/api/v1/attendances", params={"clinic_id": clinic_id})
    assert by_clinic.status_code == 200
    assert by_clinic.json()["total"] == 1
    assert by_clinic.json()["items"][0]["clinic_id"] == clinic_id

    by_owner_and_period = await client.get(
        "/api/v1/attendances",
        params={
            "owner_name": "maria sou",
            "service_date_from": "2026-01-01",
            "service_date_to": "2026-01-31",
        },
    )
    assert by_owner_and_period.status_code == 200
    assert by_owner_and_period.json()["total"] == 1
    assert by_owner_and_period.json()["items"][0]["clinic_id"] == clinic_id

    invalid_range = await client.get(
        "/api/v1/attendances",
        params={"service_date_from": "2026-02-01", "service_date_to": "2026-01-01"},
    )
    assert invalid_range.status_code == 422
    assert invalid_range.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_draft_creation_is_permission_gated_and_audited(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(client, name="Dr. Teste", crmv="CRMV-SC 00001")
    patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
    payload = {
        "clinic_id": clinic_id,
        "veterinarian_id": veterinarian_id,
        "patient_id": patient_id,
    }

    await _switch_user(client, session_factory, email="finance@vertere.local", role_id=ROLE_FINANCE)
    assert (await client.post("/api/v1/attendances/drafts", json=payload)).status_code == 403

    await _switch_user(
        client, session_factory, email="reception@vertere.local", role_id=ROLE_RECEPTION
    )
    response = await client.post("/api/v1/attendances/drafts", json=payload)
    assert response.status_code == 201
    row = _audit_row(session_factory, "attendances.draft_created")
    assert row.entity_id == response.json()["id"]


async def test_preview_charges_what_confirm_charges_without_side_effects(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    # Prévia não persiste item, não consome protocolo e não audita; também não exige
    # Idempotency-Key (é leitura, não "criação/confirmação/fechamento", rules/02-backend.md).
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    preview = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview", json=_items(exam_id, 2)
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["attendance_id"] == attendance_id
    assert (Decimal(body["grand_total"]), Decimal(body["subtotal"])) == (
        Decimal("200.00"),
        Decimal("200.00"),
    )
    assert "protocol_number" not in body
    assert "status" not in body
    stored = (await client.get(f"/api/v1/attendances/{attendance_id}")).json()
    assert (stored["status"], stored["items"]) == ("DRAFT", [])
    with session_factory() as session:
        counts = session.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM attendance_exams WHERE attendance_id = CAST(:id AS UUID)), "
                "(SELECT COUNT(*) FROM attendance_sequences), "
                "(SELECT COUNT(*) FROM audit_log WHERE entity_id = CAST(:id AS TEXT))"
            ),
            {"id": attendance_id},
        ).one()
    assert tuple(counts) == (0, 0, 1)  # só a entrada draft_created, nada da prévia

    # A prévia nunca diverge do que /confirm cobra; depois de confirmado, prévia é recusada.
    other_id, other_exam_id = await _create_confirmable_draft(client, session_factory)
    payload = _items(other_exam_id, 3)
    previewed = await client.post(f"/api/v1/attendances/{other_id}/preview", json=payload)
    confirmed = await client.post(
        f"/api/v1/attendances/{other_id}/confirm",
        json=payload,
        headers=_idempotency_header("preview-then-confirm"),
    )
    assert (previewed.status_code, confirmed.status_code) == (200, 200)
    assert previewed.json()["grand_total"] == confirmed.json()["grand_total"]
    assert previewed.json()["subtotal"] == confirmed.json()["subtotal"]
    after_confirm = await client.post(f"/api/v1/attendances/{other_id}/preview", json=payload)
    assert after_confirm.status_code == 422

    # Exame sem preço válido na data do atendimento é recusado.
    unpriced_id, unpriced_exam_id = await _create_confirmable_draft(client, session_factory)
    with session_factory.begin() as session:
        session.execute(
            text("UPDATE exams SET price_valid_from = DATE '2026-02-01' WHERE id = :id"),
            {"id": unpriced_exam_id},
        )
    unpriced = await client.post(
        f"/api/v1/attendances/{unpriced_id}/preview", json=_items(unpriced_exam_id)
    )
    assert unpriced.status_code == 422
    assert unpriced.json()["error"]["code"] == "PRICE_NOT_AVAILABLE"

    assert (
        await client.post(f"/api/v1/attendances/{uuid4()}/preview", json=_items(str(uuid4())))
    ).status_code == 404

    await _switch_user(client, session_factory, email="finance@vertere.local", role_id=ROLE_FINANCE)
    forbidden = await client.post(
        f"/api/v1/attendances/{attendance_id}/preview", json=_items(exam_id)
    )
    assert forbidden.status_code == 403


async def test_confirm_computes_protocol_totals_and_flat_on_call_fee(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)

    normal_id, normal_exam = await _create_confirmable_draft(client, session_factory)
    normal = await client.post(
        f"/api/v1/attendances/{normal_id}/confirm",
        json=_items(normal_exam, 2),
        headers=_idempotency_header("confirm-1"),
    )
    assert normal.status_code == 200
    body = normal.json()
    assert (body["status"], body["billing_competence"]) == ("CONFIRMED", "2026-01-01")
    assert (Decimal(body["grand_total"]), Decimal(body["subtotal"])) == (
        Decimal("200.00"),
        Decimal("200.00"),
    )
    assert body["protocol_number"] == "P000001/26"
    assert len(body["items"]) == 1
    assert Decimal(body["items"][0]["total_amount"]) == Decimal("200.00")

    # Taxa de plantão é fixa por atendimento (uma vez, não por exame) e a prévia já a mostra.
    # O protocolo é uma sequência do laboratório por ano, não por clínica (modelo §7).
    for service_level, fee, total, protocol in (
        ("PLANTAO_NORMAL", "100.00", "300.00", "P000002/26"),
        ("PLANTAO_ESPECIAL", "150.00", "350.00", "P000003/26"),
    ):
        attendance_id, exam_id = await _create_confirmable_draft(
            client, session_factory, service_level=service_level
        )
        payload = _items(exam_id, 2)
        preview = await client.post(f"/api/v1/attendances/{attendance_id}/preview", json=payload)
        assert Decimal(preview.json()["on_call_fee"]) == Decimal(fee)
        assert Decimal(preview.json()["grand_total"]) == Decimal(total)

        response = await client.post(
            f"/api/v1/attendances/{attendance_id}/confirm",
            json=payload,
            headers=_idempotency_header(f"confirm-{service_level}"),
        )
        assert response.status_code == 200
        confirmed = response.json()
        assert confirmed["service_level"] == service_level
        assert Decimal(confirmed["subtotal"]) == Decimal("200.00")
        assert Decimal(confirmed["surcharge_total"]) == Decimal("0.00")
        assert Decimal(confirmed["on_call_fee"]) == Decimal(fee)
        assert Decimal(confirmed["grand_total"]) == Decimal(total)
        assert confirmed["protocol_number"] == protocol

    assert _audit_row(session_factory, "attendances.confirmed").entity_id == attendance_id


async def test_confirm_is_idempotent_and_rejects_invalid_requests(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    url = f"/api/v1/attendances/{attendance_id}/confirm"
    payload = _items(exam_id)

    # Sem Idempotency-Key, sem itens e com atendimento inexistente a confirmação é recusada.
    assert (await client.post(url, json=payload)).status_code == 422
    empty = await client.post(url, json={"items": []}, headers=_idempotency_header("no-items"))
    assert empty.status_code == 422
    unknown = await client.post(
        f"/api/v1/attendances/{uuid4()}/confirm",
        json=_items(str(uuid4())),
        headers=_idempotency_header("confirm-unknown"),
    )
    assert unknown.status_code == 404

    first = await client.post(url, json=payload, headers=_idempotency_header("confirm-replay"))
    assert first.status_code == 200
    # Mesma chave e payload: repete a resposta anterior sem confirmar de novo.
    replay = await client.post(url, json=payload, headers=_idempotency_header("confirm-replay"))
    assert (replay.status_code, replay.json()) == (200, first.json())
    with session_factory() as session:
        item_count = session.execute(
            text("SELECT COUNT(*) FROM attendance_exams WHERE attendance_id = :id"),
            {"id": attendance_id},
        ).scalar_one()
    assert item_count == 1

    # Mesma chave com payload diferente é conflito.
    conflict = await client.post(
        url, json=_items(exam_id, 2), headers=_idempotency_header("confirm-replay")
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    # Chave diferente no mesmo atendimento falha na máquina de estados (já CONFIRMED), não é
    # engolida pelo replay de idempotência.
    again = await client.post(url, json=payload, headers=_idempotency_header("confirm-again"))
    assert again.status_code == 422

    other_id, other_exam_id = await _create_confirmable_draft(client, session_factory)
    await _switch_user(client, session_factory, email="finance@vertere.local", role_id=ROLE_FINANCE)
    forbidden = await client.post(
        f"/api/v1/attendances/{other_id}/confirm",
        json=_items(other_exam_id),
        headers=_idempotency_header("confirm-forbidden"),
    )
    assert forbidden.status_code == 403


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
    payload = _items(exam_id)
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
        assert row.protocol_number == "P000001/26"
        item_count = session.execute(
            text("SELECT COUNT(*) FROM attendance_exams WHERE attendance_id = :id"),
            {"id": attendance_id},
        ).scalar_one()
        assert item_count == 1


async def test_cancel_records_the_reason_and_blocks_invalid_requests(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    draft_id, _ = await _create_confirmable_draft(client, session_factory)
    confirmed_id, confirmed_exam = await _create_confirmable_draft(client, session_factory)
    confirm = await client.post(
        f"/api/v1/attendances/{confirmed_id}/confirm",
        json=_items(confirmed_exam),
        headers=_idempotency_header("cancel-after-confirm"),
    )
    assert confirm.status_code == 200
    cancel_url = f"/api/v1/attendances/{draft_id}/cancel"

    assert (
        await client.post(f"/api/v1/attendances/{uuid4()}/cancel", json={"reason": "Inexistente"})
    ).status_code == 404
    assert (await client.post(cancel_url, json={"reason": ""})).status_code == 422
    mass_assignment = await client.post(
        cancel_url, json={"reason": "Motivo válido", "status": "CONFIRMED", "grand_total": "0.00"}
    )
    assert mass_assignment.status_code == 422

    cancelled = await client.post(cancel_url, json={"reason": "Tutor desmarcou o exame"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancel_reason"] == "Tutor desmarcou o exame"
    row = _audit_row(session_factory, "attendances.cancelled")
    assert (row.entity_id, row.reason) == (draft_id, "Tutor desmarcou o exame")

    assert (await client.post(cancel_url, json={"reason": "Segundo"})).status_code == 409

    # Atendimento já confirmado também pode ser cancelado.
    after_confirm = await client.post(
        f"/api/v1/attendances/{confirmed_id}/cancel", json={"reason": "Erro de cadastro"}
    )
    assert (after_confirm.status_code, after_confirm.json()["status"]) == (200, "CANCELLED")

    other_id, _ = await _create_confirmable_draft(client, session_factory)
    await _switch_user(
        client, session_factory, email="finance-cancel@vertere.local", role_id=ROLE_FINANCE
    )
    forbidden = await client.post(
        f"/api/v1/attendances/{other_id}/cancel", json={"reason": "Tentativa sem permissão"}
    )
    assert forbidden.status_code == 403


async def test_update_uses_optimistic_locking_and_respects_the_attendance_state(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    draft_id, _ = await _create_confirmable_draft(client, session_factory)
    url = f"/api/v1/attendances/{draft_id}"

    assert (
        await client.patch(f"/api/v1/attendances/{uuid4()}", json={"row_version": 1, "notes": "x"})
    ).status_code == 404
    assert (
        await client.patch(url, json={"row_version": 999, "notes": "Não deveria passar"})
    ).status_code == 409
    mass_assignment = await client.patch(
        url,
        json={"row_version": 1, "notes": "Ok", "grand_total": "0.00", "status": "CONFIRMED"},
    )
    assert mass_assignment.status_code == 422

    # Duas edições seguidas com a versão antiga: a segunda é recusada (não é concorrência
    # real; o `row_version` do corpo é quem protege — rules/05: "nunca sobrescreve em silêncio").
    first = await client.patch(url, json={"row_version": 1, "notes": "Paciente agitado"})
    assert first.status_code == 200
    assert (first.json()["notes"], first.json()["row_version"]) == ("Paciente agitado", 2)
    assert _audit_row(session_factory, "attendances.updated").entity_id == draft_id
    stale = await client.patch(url, json={"row_version": 1, "notes": "Versão desatualizada"})
    assert stale.status_code == 409
    second = await client.patch(url, json={"row_version": 2, "notes": "Segunda edição"})
    assert (second.status_code, second.json()["row_version"]) == (200, 3)
    assert second.json()["notes"] == "Segunda edição"

    # Confirmado: tudo pode ser corrigido, com motivo obrigatório e diff na auditoria.
    confirmed_id, confirmed_exam = await _create_confirmable_draft(client, session_factory)
    confirm = await client.post(
        f"/api/v1/attendances/{confirmed_id}/confirm",
        json=_items(confirmed_exam),
        headers=_idempotency_header("update-confirmed"),
    )
    confirmed_url = f"/api/v1/attendances/{confirmed_id}"
    row_version = confirm.json()["row_version"]
    no_reason = await client.patch(
        confirmed_url, json={"row_version": row_version, "notes": "Sem motivo"}
    )
    assert no_reason.status_code == 422
    unknown_clinic = await client.patch(
        confirmed_url,
        json={"row_version": row_version, "clinic_id": str(uuid4()), "reason": "Clínica errada"},
    )
    assert unknown_clinic.status_code == 404
    noted = await client.patch(
        confirmed_url,
        json={
            "row_version": row_version,
            "notes": "Retorno em 7 dias",
            "service_level": "PLANTAO_ESPECIAL",
            "reason": "Era plantão especial",
        },
    )
    assert (noted.status_code, noted.json()["notes"], noted.json()["status"]) == (
        200,
        "Retorno em 7 dias",
        "CONFIRMED",
    )
    assert noted.json()["service_level"] == "PLANTAO_ESPECIAL"
    assert Decimal(noted.json()["on_call_fee"]) > 0
    assert Decimal(noted.json()["grand_total"]) == Decimal(confirm.json()["grand_total"]) + Decimal(
        noted.json()["on_call_fee"]
    )
    assert _audit_row(session_factory, "attendances.updated").reason == "Era plantão especial"

    # Cancelado: também pode ser corrigido (dado cadastral), com motivo.
    cancelled_id, _ = await _create_confirmable_draft(client, session_factory)
    cancelled = await client.post(
        f"/api/v1/attendances/{cancelled_id}/cancel", json={"reason": "Motivo do cancelamento"}
    )
    after_cancel = await client.patch(
        f"/api/v1/attendances/{cancelled_id}",
        json={
            "row_version": cancelled.json()["row_version"],
            "notes": "Correção cadastral",
            "reason": "Observação errada",
        },
    )
    assert (after_cancel.status_code, after_cancel.json()["status"]) == (200, "CANCELLED")

    await _switch_user(
        client, session_factory, email="finance-update@vertere.local", role_id=ROLE_FINANCE
    )
    forbidden = await client.patch(url, json={"row_version": 3, "notes": "Sem permissão"})
    assert forbidden.status_code == 403


async def test_timeline_lists_this_attendance_most_recent_first_and_paginates(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    paginated_id, _ = await _create_confirmable_draft(client, session_factory)

    confirm = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json=_items(exam_id),
        headers=_idempotency_header("timeline-confirm"),
    )
    update = await client.patch(
        f"/api/v1/attendances/{attendance_id}",
        json={
            "row_version": confirm.json()["row_version"],
            "notes": "Retorno agendado",
            "reason": "Combinado por telefone",
        },
    )
    assert (confirm.status_code, update.status_code) == (200, 200)

    timeline = await client.get(f"/api/v1/attendances/{attendance_id}/timeline")
    assert timeline.status_code == 200
    body = timeline.json()
    assert body["total"] == 3  # não mistura com as entradas do outro atendimento
    assert [item["action"] for item in body["items"]] == [
        "attendances.updated",
        "attendances.confirmed",
        "attendances.draft_created",
    ]
    assert body["items"][0]["after_state"] == {"notes": "Retorno agendado"}
    assert body["items"][0]["reason"] == "Combinado por telefone"
    assert all(item["actor_name"] for item in body["items"])  # LAB scope sees author names

    row_version = 1
    for index in range(3):
        edit = await client.patch(
            f"/api/v1/attendances/{paginated_id}",
            json={"row_version": row_version, "notes": f"Edição {index}"},
        )
        assert edit.status_code == 200
        row_version = edit.json()["row_version"]
    page = await client.get(
        f"/api/v1/attendances/{paginated_id}/timeline", params={"page": 1, "page_size": 2}
    )
    assert page.status_code == 200
    assert (page.json()["total"], len(page.json()["items"])) == (4, 2)  # draft + 3 edições
    assert (page.json()["page"], page.json()["page_size"]) == (1, 2)

    assert (await client.get(f"/api/v1/attendances/{uuid4()}/timeline")).status_code == 404
    await client.post("/api/v1/auth/logout")
    anonymous = await client.get(f"/api/v1/attendances/{attendance_id}/timeline")
    assert anonymous.status_code == 401


async def test_status_counts_bills_only_confirmed_attendances_across_the_whole_filter(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    await _create_confirmable_draft(client, session_factory)  # DRAFT: not billable
    cancelled_id, cancelled_exam = await _create_confirmable_draft(client, session_factory)
    confirmed_ids: list[str] = []
    for key, quantity in (("sc-1", 1), ("sc-2", 2)):
        attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
        confirm = await client.post(
            f"/api/v1/attendances/{attendance_id}/confirm",
            json=_items(exam_id, quantity),
            headers=_idempotency_header(key),
        )
        assert confirm.status_code == 200
        confirmed_ids.append(attendance_id)
    await client.post(
        f"/api/v1/attendances/{cancelled_id}/confirm",
        json=_items(cancelled_exam),
        headers=_idempotency_header("sc-cancelled"),
    )
    cancel = await client.post(
        f"/api/v1/attendances/{cancelled_id}/cancel", json={"reason": "Tutor desistiu"}
    )
    assert cancel.status_code == 200

    # 100,00 + 200,00 confirmados; rascunho e cancelado não entram no valor.
    counts = await client.get("/api/v1/attendances/status-counts")
    assert counts.status_code == 200
    body = counts.json()
    assert body["by_status"] == {"DRAFT": 1, "CONFIRMED": 2, "CANCELLED": 1}
    assert Decimal(body["billed_total"]) == Decimal("300.00")

    # O filtro vale para o total inteiro, não só para uma página.
    in_range = await client.get(
        "/api/v1/attendances/status-counts",
        params={"service_date_from": "2026-01-05", "service_date_to": "2026-01-05"},
    )
    assert Decimal(in_range.json()["billed_total"]) == Decimal("300.00")
    out_of_range = await client.get(
        "/api/v1/attendances/status-counts", params={"service_date_from": "2026-02-01"}
    )
    assert Decimal(out_of_range.json()["billed_total"]) == Decimal("0")
    assert (
        await client.get(
            "/api/v1/attendances/status-counts",
            params={"service_date_from": "2026-02-01", "service_date_to": "2026-01-01"},
        )
    ).status_code == 422


async def test_panel_item_freezes_its_composition_on_the_attendance(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, hemograma_id = await _create_confirmable_draft(client, session_factory)
    species_id = _get_species_id(session_factory, name="Canino")
    category_id = await _create_exam_category(client, f"Perfis {uuid4().hex[:6]}")
    alt_response = await client.post(
        "/api/v1/exams",
        json={
            "name": "ALT",
            "category_id": category_id,
            "price_base": "30.00",
            "species_ids": [species_id],
        },
    )
    assert alt_response.status_code == 201
    panel_response = await client.post(
        "/api/v1/exams",
        json={
            "name": "BÁSICO 1",
            "category_id": category_id,
            "price_base": "110.00",
            "species_ids": [species_id],
            "component_exam_ids": [hemograma_id, alt_response.json()["id"]],
        },
    )
    assert panel_response.status_code == 201
    panel = panel_response.json()

    # Pacote + exame avulso no mesmo atendimento; o total usa o preço do pacote.
    confirmed = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={
            "items": [
                {"exam_id": panel["id"], "quantity": 1},
                {"exam_id": alt_response.json()["id"], "quantity": 1},
            ]
        },
        headers=_idempotency_header("panel-confirm"),
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert Decimal(body["subtotal"]) == Decimal("140.00")
    by_name = {item["exam_name"]: item for item in body["items"]}
    assert [c["name"] for c in by_name["BÁSICO 1"]["components"]] == ["Hemograma", "ALT"]
    assert by_name["ALT"]["components"] == []

    # Editar o pacote depois não reescreve o que o atendimento já continha.
    edited = await client.patch(
        f"/api/v1/exams/{panel['id']}",
        json={
            "name": "BÁSICO 1",
            "category_id": category_id,
            "price_base": "999.00",
            "species_ids": [species_id],
            "component_exam_ids": [alt_response.json()["id"]],
            "status": "ACTIVE",
            "expected_row_version": panel["row_version"],
            "reason": "Reajuste do pacote",
        },
    )
    assert edited.status_code == 200
    reread = await client.get(f"/api/v1/attendances/{attendance_id}")
    frozen = {item["exam_name"]: item for item in reread.json()["items"]}["BÁSICO 1"]
    assert [c["name"] for c in frozen["components"]] == ["Hemograma", "ALT"]
    assert Decimal(frozen["price_base"]) == Decimal("110.00")


async def test_exams_can_be_added_removed_and_corrected_after_confirmation(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, first_exam = await _create_confirmable_draft(
        client, session_factory, service_level="PLANTAO_NORMAL"
    )
    unique = uuid4().hex[:8]
    second_exam = await _create_exam(
        client,
        code=f"UREIA-{unique}",
        category_id=await _create_exam_category(client, f"Bioquímica {unique}"),
        price_base="50.00",
        species_ids=[_get_species_id(session_factory, name="Canino")],
    )
    confirm = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json=_items(first_exam, 2),
        headers=_idempotency_header("items-edit-confirm"),
    )
    assert confirm.status_code == 200
    first_item = confirm.json()["items"][0]["id"]
    assert Decimal(confirm.json()["grand_total"]) == Decimal("300.00")  # 2 x 100 + plantão 100
    url = f"/api/v1/attendances/{attendance_id}/items"

    # Motivo é obrigatório e a versão precisa ser a atual.
    assert (await client.put(url, json={"row_version": 2, "items": []})).status_code == 422
    stale = await client.put(
        url,
        json={"row_version": 1, "reason": "x", "items": [{"item_id": first_item}]},
    )
    assert stale.status_code == 409

    # Corrige a quantidade, dá desconto e inclui um exame depois do fato.
    edited = await client.put(
        url,
        json={
            "row_version": confirm.json()["row_version"],
            "reason": "Solicitante pediu mais um exame e combinou cortesia",
            "items": [
                {
                    "item_id": first_item,
                    "quantity": 1,
                    "discount_amount": "20.00",
                    "override_reason": "Cortesia",
                },
                {"exam_id": second_exam, "quantity": 3},
            ],
        },
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert (body["status"], len(body["items"])) == ("CONFIRMED", 2)
    assert Decimal(body["subtotal"]) == Decimal("250.00")  # 100 + 3 x 50
    assert Decimal(body["discount_total"]) == Decimal("20.00")
    assert Decimal(body["grand_total"]) == Decimal("330.00")  # 80 + 150 + plantão 100
    assert sum(Decimal(item["total_amount"]) for item in body["items"]) + Decimal(
        body["on_call_fee"]
    ) == Decimal(body["grand_total"])
    assert body["row_version"] > confirm.json()["row_version"]
    audit = _audit_row(session_factory, "attendances.items_updated")
    assert audit.entity_id == attendance_id
    assert audit.reason == "Solicitante pediu mais um exame e combinou cortesia"

    # Remover não apaga: o item fica no histórico como CANCELLED e sai do total.
    second_item = next(i["id"] for i in body["items"] if i["exam_id"] == second_exam)
    removed = await client.put(
        url,
        json={
            "row_version": body["row_version"],
            "reason": "Primeiro exame lançado por engano",
            "items": [{"item_id": second_item, "quantity": 3}],
        },
    )
    assert removed.status_code == 200
    statuses = {i["exam_id"]: i["status"] for i in removed.json()["items"]}
    assert statuses == {first_exam: "CANCELLED", second_exam: "ACTIVE"}
    assert Decimal(removed.json()["grand_total"]) == Decimal("250.00")  # 150 + plantão 100

    # Nunca fica sem exame; item de outro atendimento é recusado.
    version = removed.json()["row_version"]
    empty = await client.put(url, json={"row_version": version, "reason": "Limpar", "items": []})
    assert empty.status_code == 422
    foreign = await client.put(
        url,
        json={"row_version": version, "reason": "Teste", "items": [{"item_id": str(uuid4())}]},
    )
    assert foreign.status_code == 422

    # Reativar o item removido (continua com o preço do snapshot) e corrigir cancelado.
    cancelled = await client.post(
        f"/api/v1/attendances/{attendance_id}/cancel",
        json={"reason": "Lançado errado"},
    )
    assert cancelled.status_code == 200, cancelled.text
    restored = await client.put(
        url,
        json={
            "row_version": cancelled.json()["row_version"],
            "reason": "Era o primeiro exame mesmo",
            "items": [{"item_id": first_item, "quantity": 1}],
        },
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "CANCELLED"
    assert Decimal(restored.json()["grand_total"]) == Decimal("200.00")  # 100 + plantão 100


async def test_item_discount_needs_override_permission_but_other_edits_do_not(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    confirm = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json=_items(exam_id, 1),
        headers=_idempotency_header("items-perm-confirm"),
    )
    item_id = confirm.json()["items"][0]["id"]
    url = f"/api/v1/attendances/{attendance_id}/items"
    version = confirm.json()["row_version"]

    await _switch_user(
        client, session_factory, email="reception2@vertere.local", role_id=ROLE_RECEPTION
    )
    discount = await client.put(
        url,
        json={
            "row_version": version,
            "reason": "Desconto",
            "items": [{"item_id": item_id, "discount_amount": "10.00", "override_reason": "x"}],
        },
    )
    assert discount.status_code == 403

    # Quantidade (sem mexer no desconto) a recepção pode corrigir.
    quantity = await client.put(
        url,
        json={
            "row_version": version,
            "reason": "Eram dois",
            "items": [{"item_id": item_id, "quantity": 2}],
        },
    )
    assert quantity.status_code == 200
    assert Decimal(quantity.json()["grand_total"]) == Decimal("200.00")


async def test_money_is_withheld_from_users_without_pricing_read(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    attendance_id, exam_id = await _create_confirmable_draft(client, session_factory)
    confirm = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json=_items(exam_id, 1),
        headers=_idempotency_header("money-confirm"),
    )
    item_id = confirm.json()["items"][0]["id"]
    url = f"/api/v1/attendances/{attendance_id}/items"
    discounted = await client.put(
        url,
        json={
            "row_version": confirm.json()["row_version"],
            "reason": "Desconto combinado",
            "items": [{"item_id": item_id, "discount_amount": "10.00", "override_reason": "x"}],
        },
    )
    assert discounted.status_code == 200
    grand_total = discounted.json()["grand_total"]
    assert grand_total is not None

    no_price_role = uuid4()
    with session_factory() as session:
        now = datetime.now(UTC)
        session.add(RoleModel(id=no_price_role, name="Operação sem valor", scope="LAB"))
        session.flush()
        for code in ("attendances.read", "attendances.update"):
            permission = session.query(PermissionModel).filter_by(code=code).one()
            session.add(
                RolePermissionModel(
                    role_id=no_price_role, permission_id=permission.id, granted_at=now
                )
            )
        session.commit()
    await _switch_user(
        client, session_factory, email="semvalor@vertere.local", role_id=no_price_role
    )

    detail = (await client.get(f"/api/v1/attendances/{attendance_id}")).json()
    money_fields = ("subtotal", "discount_total", "surcharge_total", "on_call_fee", "grand_total")
    assert all(detail[field] is None for field in money_fields)
    assert all(
        item[field] is None
        for item in detail["items"]
        for field in ("price_base", "discount_amount", "surcharge_amount", "total_amount")
    )
    listed = (await client.get("/api/v1/attendances")).json()
    assert all(row["grand_total"] is None for row in listed["items"])
    assert (await client.get("/api/v1/attendances/status-counts")).json()["billed_total"] is None
    timeline = (await client.get(f"/api/v1/attendances/{attendance_id}/timeline")).json()
    assert "grand_total" not in str(timeline) and "discount_amount" not in str(timeline)

    # Corrigir a quantidade sem ver valor não pode apagar o desconto já aplicado.
    edited = await client.put(
        url,
        json={
            "row_version": detail["row_version"],
            "reason": "Eram dois",
            "items": [{"item_id": item_id, "quantity": 2}],
        },
    )
    assert edited.status_code == 200
    assert edited.json()["grand_total"] is None

    await client.post("/api/v1/auth/logout")
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    after = (await client.get(f"/api/v1/attendances/{attendance_id}")).json()
    assert after["items"][0]["quantity"] == 2
    assert Decimal(after["items"][0]["discount_amount"]) == Decimal("10.00")
    assert Decimal(after["grand_total"]) == Decimal(grand_total) + Decimal("100.00")
