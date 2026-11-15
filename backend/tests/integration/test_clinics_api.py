"""Integração com PostgreSQL real (Testcontainers) — CRUD, autorização,
CNPJ duplicado e soft delete, ponta a ponta via HTTPX/ASGI.
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


async def test_clinic_creation_is_permission_gated_unique_and_validates_fields(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    assert (await client.get("/api/v1/clinics")).status_code == 401

    await _login_as(
        client, session_factory, email="technical@vertere.local", role_id=ROLE_TECHNICAL
    )
    denied = await client.post("/api/v1/clinics", json={"name": "Clínica Sem Permissão"})
    assert denied.status_code == 403

    # Regressão da migration 0004 — RECEPTION só tinha `clinics.read` no seed 0002.
    await _login_as(
        client, session_factory, email="reception@vertere.local", role_id=ROLE_RECEPTION
    )
    by_reception = await client.post("/api/v1/clinics", json={"name": "Bea Pet Center"})
    assert by_reception.status_code == 201

    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    created = await client.post(
        "/api/v1/clinics",
        json={
            "name": "Schweitzer",
            "tax_id": "78.977.352/0001-99",
            "phone": "(47) 9 9914-6833",
            "email": "clinicavetschweitzer@gmail.com",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["name"], body["tax_id"], body["status"]) == (
        "Schweitzer",
        "78977352000199",
        "ACTIVE",
    )
    fetched = await client.get(f"/api/v1/clinics/{body['id']}")
    assert (fetched.status_code, fetched.json()["name"]) == (200, "Schweitzer")

    duplicate = await client.post(
        "/api/v1/clinics", json={"name": "Clínica B", "tax_id": "78977352000199"}
    )
    assert duplicate.status_code == 409

    for field, value in (("tax_id", "123"), ("address_state", "Santa Catarina")):
        invalid = await client.post(
            "/api/v1/clinics", json={"name": "Clínica Inválida", field: value}
        )
        assert invalid.status_code == 422, field
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR", field


async def test_clinic_updates_use_row_versions_and_deactivation_preserves_the_record(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    created = (await client.post("/api/v1/clinics", json={"name": "Bicho Urbano"})).json()
    url = f"/api/v1/clinics/{created['id']}"

    stale = await client.patch(
        url, json={"name": "Renomeada", "status": "ACTIVE", "expected_row_version": 99}
    )
    assert stale.status_code == 409

    # Versões encadeadas usam a devolvida pela edição anterior.
    versions = [created["row_version"]]
    for name in ("Versao Um", "Versao Dois"):
        update = await client.patch(
            url, json={"name": name, "status": "ACTIVE", "expected_row_version": versions[-1]}
        )
        assert update.status_code == 200
        versions.append(update.json()["row_version"])
    assert versions == [
        created["row_version"],
        created["row_version"] + 1,
        created["row_version"] + 2,
    ]

    deactivated = await client.post(f"{url}/deactivate")
    assert (deactivated.status_code, deactivated.json()["status"]) == (200, "INACTIVE")
    kept = await client.get(url)
    assert (kept.status_code, kept.json()["name"]) == (200, "Versao Dois")


async def test_clinic_payload_is_bounded_and_the_masked_zip_code_is_normalized(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="lab@vertere.local", role_id=ROLE_LAB_ADMIN)

    masked = await client.post(
        "/api/v1/clinics", json={"name": "  Clínica CEP  ", "address_zip_code": "12345-678"}
    )
    assert masked.status_code == 201
    assert masked.json()["address_zip_code"] == "12345678"
    assert masked.json()["name"] == "Clínica CEP"

    oversized = [
        {"name": "N" * 1_000_000},
        {"name": "ok", "notes": "x" * 2_000_000},
        {"name": "ok", "phone": "9" * 5_000},
        {"name": "ok", "address_zip_code": "1234567890123"},
        {"name": "ok", "address_zip_code": "123"},
        {"name": "ok", "email": "nao-e-email"},
        {"name": "   "},
    ]
    for payload in oversized:
        assert (await client.post("/api/v1/clinics", json=payload)).status_code == 422
