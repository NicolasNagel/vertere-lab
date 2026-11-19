"""Integração com PostgreSQL real (Testcontainers) — CRUD, autorização,
CRMV duplicado e soft delete, ponta a ponta via HTTPX/ASGI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_RECEPTION, ROLE_TECHNICAL

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM veterinarian_clinics"))
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


async def _login_as(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, email: str, role_id: UUID
) -> None:
    _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": "s3nhaForte!", "remember_me": False},
    )
    assert response.status_code == 200


async def test_veterinarian_creation_is_permission_gated_unique_and_requires_clinic_unless_autonomous(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    assert (await client.get("/api/v1/veterinarians")).status_code == 401

    await _login_as(
        client, session_factory, email="technical@vertere.local", role_id=ROLE_TECHNICAL
    )
    denied = await client.post(
        "/api/v1/veterinarians", json={"name": "Vet Sem Permissão", "crmv": "CRMV-SC 00001"}
    )
    assert denied.status_code == 403

    await _login_as(
        client, session_factory, email="reception@vertere.local", role_id=ROLE_RECEPTION
    )
    by_reception = await client.post(
        "/api/v1/veterinarians",
        json={"name": "Dra. Recepção", "crmv": "CRMV-SC 00002", "is_autonomous": True},
    )
    assert by_reception.status_code == 201

    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    created = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": "Dra. Fabianna Garcia",
            "crmv": "crmv-sc 04567",
            "phone": "(47) 9 9914-6833",
            "email": "fabianna@vertere.local",
            "is_autonomous": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["name"], body["crmv"], body["is_autonomous"], body["status"]) == (
        "Dra. Fabianna Garcia",
        "CRMV-SC 04567",
        True,
        "ACTIVE",
    )
    fetched = await client.get(f"/api/v1/veterinarians/{body['id']}")
    assert (fetched.status_code, fetched.json()["name"]) == (200, "Dra. Fabianna Garcia")

    duplicate = await client.post(
        "/api/v1/veterinarians",
        json={"name": "Vet B", "crmv": "CRMV-SC 04567", "is_autonomous": True},
    )
    assert duplicate.status_code == 409

    # ADR-003: não autônomo sem clínica é rejeitado de ponta a ponta.
    no_clinic = await client.post(
        "/api/v1/veterinarians",
        json={"name": "Vet Sem Clínica", "crmv": "CRMV-SC 04570", "is_autonomous": False},
    )
    assert no_clinic.status_code == 422


async def test_veterinarian_clinic_links_availability_versions_and_deactivation(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    clinic_a = (await client.post("/api/v1/clinics", json={"name": "Clinica A"})).json()
    clinic_b = (await client.post("/api/v1/clinics", json={"name": "Clinica B"})).json()

    await client.post(
        "/api/v1/veterinarians",
        json={"name": "Dra. Autonoma", "crmv": "CRMV-SC 09001", "is_autonomous": True},
    )
    linked = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": "Dr. Vinculado A",
            "crmv": "CRMV-SC 09002",
            "is_autonomous": False,
            "clinic_ids": [clinic_a["id"]],
        },
    )
    assert linked.status_code == 201
    linked_body = linked.json()

    # O vínculo vem no detalhe e a clínica única é a principal.
    detail = (await client.get(f"/api/v1/veterinarians/{linked_body['id']}")).json()
    assert [(c["clinic_id"], c["primary_clinic"]) for c in detail["clinics"]] == [
        (clinic_a["id"], True)
    ]

    # Regressão: a lista "disponíveis para a clínica" é filtrada no servidor
    # (autônomos + vinculados), a mesma regra revalidada em `/confirm`.
    for clinic, expected in (
        (clinic_a, {"Dra. Autonoma", "Dr. Vinculado A"}),
        (clinic_b, {"Dra. Autonoma"}),
    ):
        available = await client.get(
            "/api/v1/veterinarians", params={"available_for_clinic_id": clinic["id"]}
        )
        assert {item["name"] for item in available.json()["items"]} == expected, clinic["name"]

    # Versão errada conflita; versões encadeadas usam a devolvida pela edição anterior.
    url = f"/api/v1/veterinarians/{linked_body['id']}"
    base = {
        "crmv": "CRMV-SC 09002",
        "is_autonomous": False,
        "status": "ACTIVE",
        "reason": "Correção cadastral",
    }
    stale = await client.patch(url, json={**base, "name": "Renomeado", "expected_row_version": 99})
    assert stale.status_code == 409
    no_reason = {key: value for key, value in base.items() if key != "reason"}
    missing_reason = await client.patch(
        url,
        json={
            **no_reason,
            "name": "Sem motivo",
            "expected_row_version": linked_body["row_version"],
        },
    )
    assert missing_reason.status_code == 422
    versions = [linked_body["row_version"]]
    for name in ("Vet Um", "Vet Dois"):
        update = await client.patch(
            url, json={**base, "name": name, "expected_row_version": versions[-1]}
        )
        assert update.status_code == 200
        versions.append(update.json()["row_version"])
    assert versions == [
        linked_body["row_version"],
        linked_body["row_version"] + 1,
        linked_body["row_version"] + 2,
    ]

    # Desativar preserva o registro.
    deactivated = await client.post(f"{url}/deactivate")
    assert (deactivated.status_code, deactivated.json()["status"]) == (200, "INACTIVE")
    kept = await client.get(url)
    assert (kept.status_code, kept.json()["name"]) == (200, "Vet Dois")


async def test_veterinarian_input_is_trimmed_bounded_and_blank_crmv_is_a_422_not_a_500(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """QA 2026-11-19: a whitespace-only CRMV raised a bare ValueError (500); an invalid e-mail and
    unbounded text were stored as sent."""
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    body = {"name": "Dra. QA", "crmv": "CRMV-SC 77001", "is_autonomous": True}

    for field, value in (
        ("name", "   "),
        ("name", "x" * 201),
        ("crmv", "   "),
        ("crmv", "9" * 51),
        ("email", "not-an-email"),
        ("email", "a" * 250 + "@x.com"),
        ("phone", "9" * 31),
        ("notes", "n" * 2001),
    ):
        rejected = await client.post("/api/v1/veterinarians", json={**body, field: value})
        assert rejected.status_code == 422, (field, len(value))

    created = await client.post("/api/v1/veterinarians", json={**body, "name": "  Dra. QA  "})
    assert created.status_code == 201
    assert created.json()["name"] == "Dra. QA"

    update = {
        "name": "Dra. QA",
        "crmv": "   ",
        "status": "ACTIVE",
        "expected_row_version": created.json()["row_version"],
        "reason": "teste",
    }
    blank_crmv = await client.patch(f"/api/v1/veterinarians/{created.json()['id']}", json=update)
    assert blank_crmv.status_code == 422
