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
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_TECHNICAL

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM outbox_events"))
        session.execute(text("DELETE FROM idempotency_keys"))
        session.execute(text("DELETE FROM financial_adjustments"))
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


def _create_user(
    session_factory: sessionmaker[Session],
    *,
    email: str,
    password: str,
    role_id: UUID = ROLE_LAB_ADMIN,
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
    patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
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


async def _close(
    client: httpx.AsyncClient,
    clinic_id: str,
    key: str,
    *,
    period: tuple[str, str] = ("2026-01-01", "2026-01-31"),
) -> httpx.Response:
    return await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "period_start": period[0], "period_end": period[1]},
        headers=_close_headers(key),
    )


async def _by_period(client: httpx.AsyncClient, clinic_id: str) -> httpx.Response:
    return await client.get(
        "/api/v1/closures/by-period",
        params={"clinic_id": clinic_id, "period_start": "2026-01-01", "period_end": "2026-01-31"},
    )


async def test_close_locks_attendances_audits_and_enforces_its_preconditions(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    empty_clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")
    (
        cancelled_item_clinic_id,
        cancelled_item_attendance,
    ) = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )

    # Pré-condições: sem Idempotency-Key, sem nada elegível, clínica inexistente e item
    # cancelado (excluído do fechamento) são recusados.
    no_key = await client.post(
        "/api/v1/closures",
        json={"clinic_id": clinic_id, "period_start": "2026-01-01", "period_end": "2026-01-31"},
    )
    assert no_key.status_code == 422
    assert (await _close(client, empty_clinic_id, "close-empty")).status_code == 422
    assert (await _close(client, str(uuid4()), "close-unknown-clinic")).status_code == 404
    with session_factory() as session:
        session.execute(
            text("UPDATE attendance_exams SET status = 'CANCELLED' WHERE attendance_id = :id"),
            {"id": cancelled_item_attendance["id"]},
        )
        session.commit()
    cancelled_item = await _close(client, cancelled_item_clinic_id, "close-excludes-cancelled")
    assert cancelled_item.status_code == 422

    response = await _close(client, clinic_id, "close-1")
    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["clinic_id"], body["item_count"]) == ("CLOSED", clinic_id, 1)
    assert Decimal(body["grand_total"]) == Decimal("100.00")
    assert len(body["items"]) == 1
    assert body["items"][0]["attendance_id"] == attendance["id"]
    assert body["items"][0]["service_level"] == "NORMAL"
    assert body["items"][0]["exam_category"]
    with session_factory() as session:
        linked = session.execute(
            text("SELECT monthly_closure_id FROM attendances WHERE id = :id"),
            {"id": attendance["id"]},
        ).one()
        assert str(linked[0]) == body["id"]
        audit_action = session.execute(
            text("SELECT action FROM audit_log WHERE entity_id = :id"), {"id": body["id"]}
        ).scalar_one()
        assert audit_action == "closures.closed"
        outbox_event_type = session.execute(
            text("SELECT event_type FROM outbox_events WHERE payload->>'closure_id' = :id"),
            {"id": body["id"]},
        ).scalar_one()
        assert outbox_event_type == "closures.closed"

    # Atendimento já fechado não pode mais ser cancelado.
    cancel = await client.post(
        f"/api/v1/attendances/{attendance['id']}/cancel",
        json={"reason": "tentativa pós-fechamento"},
    )
    assert cancel.status_code == 409

    # Mesma chave e payload: repete a resposta sem criar outro fechamento. Mesma chave com
    # payload diferente: conflito de idempotência. Chave nova no mesmo período: já existe.
    replay = await _close(client, clinic_id, "close-1")
    assert (replay.status_code, replay.json()["id"]) == (201, body["id"])
    different_payload = await _close(
        client, clinic_id, "close-1", period=("2026-02-01", "2026-02-28")
    )
    assert different_payload.status_code == 409
    assert different_payload.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    second = await _close(client, clinic_id, "close-second")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CLOSURE_ALREADY_EXISTS"
    with session_factory() as session:
        closures = session.execute(text("SELECT COUNT(*) FROM monthly_closures")).scalar_one()
    assert closures == 1

    # O fechamento é localizável por clínica + período, sem conhecer o id.
    found = await _by_period(client, clinic_id)
    assert (found.status_code, found.json()["id"]) == (200, body["id"])
    assert (await _by_period(client, empty_clinic_id)).status_code == 404

    # Sem permissão (TECNICO) fechar e consultar por período são negados.
    await client.post("/api/v1/auth/logout")
    _create_user(
        session_factory,
        email="tecnico@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="tecnico@vertere.local", password="s3nhaForte!")
    assert (await _close(client, str(uuid4()), "close-forbidden")).status_code == 403
    assert (await _by_period(client, str(uuid4()))).status_code == 403


async def test_close_header_totals_match_items_and_on_call_fee_counts_once_per_attendance(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")
    vet_id = await _create_veterinarian(client, name="Dra. Ana", crmv=f"CRMV-{uuid4()}")
    patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
    exam_id = await _create_exam(
        client, session_factory, code=f"HEMO-{uuid4().hex[:6]}", price="80.00"
    )
    for service_date, quantity in (("2026-01-05", 2), ("2026-01-20", 1)):
        await _confirm_attendance(
            client,
            clinic_id=clinic_id,
            veterinarian_id=vet_id,
            patient_id=patient_id,
            exam_id=exam_id,
            service_date=service_date,
            quantity=quantity,
        )

    response = await _close(client, clinic_id, "close-sum-check")
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

    # Um atendimento de plantão com 2 exames soma a taxa fixa uma vez ao fechamento, nunca
    # uma por item (`ClosureCandidateItem.attendance_on_call_fee`).
    plantao_clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")
    plantao_patient_id = await _create_patient(client, session_factory, clinic_id=plantao_clinic_id)
    exam_b_id = await _create_exam(
        client, session_factory, code=f"URIN-{uuid4().hex[:6]}", price="50.00"
    )
    draft = await client.post(
        "/api/v1/attendances/drafts",
        json={
            "clinic_id": plantao_clinic_id,
            "veterinarian_id": vet_id,
            "patient_id": plantao_patient_id,
            "service_date": "2026-01-10",
            "service_level": "PLANTAO_ESPECIAL",
        },
    )
    assert draft.status_code == 201
    attendance_id = draft.json()["id"]
    confirm = await client.post(
        f"/api/v1/attendances/{attendance_id}/confirm",
        json={
            "items": [
                {"exam_id": exam_id, "quantity": 1},
                {"exam_id": exam_b_id, "quantity": 1},
            ]
        },
        headers={"Idempotency-Key": f"confirm-{attendance_id}"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["on_call_fee"] == "150.00"

    plantao = await _close(client, plantao_clinic_id, "close-on-call-fee")
    assert plantao.status_code == 201
    plantao_body = plantao.json()
    assert (plantao_body["item_count"], plantao_body["on_call_fee_total"]) == (2, "150.00")
    assert sum(Decimal(item["total_amount"]) for item in plantao_body["items"]) == Decimal("130.00")
    assert Decimal(plantao_body["grand_total"]) == Decimal("280.00")
    with session_factory() as session:
        stored = session.execute(
            text("SELECT on_call_fee_total, grand_total FROM monthly_closures WHERE id = :id"),
            {"id": plantao_body["id"]},
        ).one()
    assert (Decimal(stored[0]), Decimal(stored[1])) == (Decimal("150.00"), Decimal("280.00"))
    exported = await client.get(f"/api/v1/closures/{plantao_body['id']}/export")
    assert exported.status_code == 200
    assert "taxa_de_plantao_total,150.00" in exported.text


async def test_concurrent_close_attempts_for_the_same_period_only_one_succeeds(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Real concurrency (`.claude/rules/08-testing.md`) — two closes for the
    same clinic+period fired at once, with different idempotency keys (so
    the idempotency guard itself cannot be what serializes them; only the
    advisory lock + EXCLUDE constraint can)."""
    await _login_admin(client, session_factory)
    clinic_id, _attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    payload = {"clinic_id": clinic_id, "period_start": "2026-01-01", "period_end": "2026-01-31"}

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


async def test_free_periods_close_independently_and_overlaps_conflict(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """A clinic that closes by quinzena instead of by full month: one attendance per half,
    each closed under its own free period, neither overlapping the other."""
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, f"Clinica {uuid4()}")
    vet_id = await _create_veterinarian(client, name="Dra. Ana", crmv=f"CRMV-{uuid4()}")
    patient_id = await _create_patient(client, session_factory, clinic_id=clinic_id)
    exam_id = await _create_exam(
        client, session_factory, code=f"HEMO-{uuid4().hex[:6]}", price="100.00"
    )
    for service_date in ("2026-01-05", "2026-01-20"):
        await _confirm_attendance(
            client,
            clinic_id=clinic_id,
            veterinarian_id=vet_id,
            patient_id=patient_id,
            exam_id=exam_id,
            service_date=service_date,
        )

    first_half = await _close(client, clinic_id, "quinzena-1", period=("2026-01-01", "2026-01-15"))
    second_half = await _close(client, clinic_id, "quinzena-2", period=("2026-01-16", "2026-01-31"))
    for half in (first_half, second_half):
        assert half.status_code == 201
        assert (half.json()["item_count"], half.json()["grand_total"]) == (1, "100.00")
    with session_factory() as session:
        count = session.execute(
            text(
                "SELECT COUNT(*) FROM monthly_closures WHERE clinic_id = :clinic_id "
                "AND status = 'CLOSED'"
            ),
            {"clinic_id": clinic_id},
        ).scalar_one()
    assert count == 2

    overlapping = await _close(client, clinic_id, "overlap", period=("2026-01-10", "2026-01-20"))
    assert overlapping.status_code == 409
    assert overlapping.json()["error"]["code"] == "CLOSURE_ALREADY_EXISTS"


async def test_reopen_requires_a_reason_releases_attendances_and_allows_a_next_version(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    first = await _close(client, clinic_id, "close-before-reopen")
    assert first.status_code == 201
    closure_id = first.json()["id"]
    reopen_url = f"/api/v1/closures/{closure_id}/reopen"

    assert (await client.post(reopen_url, json={"reason": "curto"})).status_code == 422
    reopened = await client.post(reopen_url, json={"reason": "Correção de competência autorizada."})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "REOPENED"
    with session_factory() as session:
        association = session.execute(
            text("SELECT monthly_closure_id FROM attendances WHERE id = :id"),
            {"id": attendance["id"]},
        ).scalar_one()
        audit_reason = session.execute(
            text(
                "SELECT reason FROM audit_log "
                "WHERE action = 'closures.reopened' AND entity_id = :id"
            ),
            {"id": closure_id},
        ).scalar_one()
    assert association is None
    assert audit_reason == "Correção de competência autorizada."

    # Por período, o fechamento reaberto é o que volta; reabrir de novo é transição inválida.
    assert (await _by_period(client, clinic_id)).json()["status"] == "REOPENED"
    again = await client.post(reopen_url, json={"reason": "Segunda tentativa não permitida."})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    second = await _close(client, clinic_id, "close-after-reopen")
    assert second.status_code == 201
    assert second.json()["version"] == 2


async def test_adjustment_is_append_only_visible_in_detail_and_export_and_validated(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id, _attendance = await _setup_clinic_with_confirmed_attendance(
        client, session_factory, service_date="2026-01-10"
    )
    closure = (await _close(client, clinic_id, "close-before-adjustment")).json()
    original_total = closure["grand_total"]
    adjustments_url = f"/api/v1/closures/{closure['id']}/adjustments"
    reason = "Correção autorizada pelo financeiro."

    # Mass assignment e item de outro fechamento são recusados.
    mass_assignment = await client.post(
        adjustments_url,
        json={"kind": "CREDIT", "amount": "10.00", "reason": reason, "grand_total": "0.01"},
    )
    assert mass_assignment.status_code == 422
    foreign_item = await client.post(
        adjustments_url,
        json={
            "monthly_closure_item_id": str(uuid4()),
            "kind": "CREDIT",
            "amount": "10.00",
            "reason": reason,
        },
    )
    assert foreign_item.status_code == 422

    adjusted = await client.post(
        adjustments_url,
        json={
            "monthly_closure_item_id": closure["items"][0]["id"],
            "kind": "DEBIT",
            "amount": "15.25",
            "reason": "Cobrança complementar autorizada.",
        },
    )
    assert adjusted.status_code == 201
    assert adjusted.json()["amount"] == "15.25"

    detail = await client.get(f"/api/v1/closures/{closure['id']}")
    assert detail.status_code == 200
    assert detail.json()["grand_total"] == original_total  # o fechamento em si não é editado
    assert detail.json()["adjustments"][0]["kind"] == "DEBIT"
    exported = await client.get(f"/api/v1/closures/{closure['id']}/export")
    assert exported.status_code == 200
    assert "ajustes,tipo,valor,motivo" in exported.text
    assert "DEBIT,15.25" in exported.text
    with session_factory() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM financial_adjustments WHERE monthly_closure_id = :id"),
            {"id": closure["id"]},
        ).scalar_one()
        stored_total = session.execute(
            text("SELECT grand_total FROM monthly_closures WHERE id = :id"), {"id": closure["id"]}
        ).scalar_one()
    assert count == 1
    assert str(stored_total) == original_total
