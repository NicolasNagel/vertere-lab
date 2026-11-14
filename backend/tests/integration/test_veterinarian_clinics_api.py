"""Integração com PostgreSQL real (Testcontainers) — vínculo N:N
veterinário-clínica: link, unlink, idempotência, autorização e a regra
"não autônomo exige ao menos uma clínica", ponta a ponta via HTTPX/ASGI.
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
from app.modules.identity.infrastructure.models import (
    ClinicMembershipModel,
    LabMembershipModel,
    PermissionModel,
    RolePermissionModel,
    UserModel,
)
from app.modules.identity.infrastructure.seed import (
    ROLE_CLINIC_ADMIN,
    ROLE_LAB_ADMIN,
    ROLE_TECHNICAL,
)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


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
    # Autonomous by default: most tests here exercise the link/unlink
    # endpoints as a separate step and don't care about the "non-autonomous
    # needs >=1 clinic at creation" rule, which has its own dedicated tests
    # in test_veterinarians_api.py.
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


async def test_veterinarian_clinic_links_are_bidirectional_idempotent_guarded_and_permissioned(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    clinic_id = await _create_clinic(client, "Schweitzer")
    veterinarian_id = await _create_veterinarian(
        client, name="Dra. Fabianna Garcia", crmv="CRMV-SC 04567"
    )
    link_url = f"/api/v1/veterinarians/{veterinarian_id}/clinics"

    # Vínculo aparece nos dois lados.
    linked = await client.post(link_url, json={"clinic_id": clinic_id, "primary": True})
    assert linked.status_code == 204
    vet_detail = await client.get(f"/api/v1/veterinarians/{veterinarian_id}")
    assert vet_detail.json()["clinics"] == [
        {"clinic_id": clinic_id, "clinic_name": "Schweitzer", "primary_clinic": True}
    ]
    clinic_detail = await client.get(f"/api/v1/clinics/{clinic_id}")
    assert clinic_detail.json()["veterinarians"] == [
        {
            "veterinarian_id": veterinarian_id,
            "veterinarian_name": "Dra. Fabianna Garcia",
            "crmv": "CRMV-SC 04567",
            "primary_clinic": True,
        }
    ]

    # Repetir o vínculo é idempotente.
    again = await client.post(link_url, json={"clinic_id": clinic_id, "primary": True})
    assert again.status_code == 204
    after_repeat = await client.get(f"/api/v1/veterinarians/{veterinarian_id}")
    assert len(after_repeat.json()["clinics"]) == 1

    # Sem permissão (técnico) o vínculo é negado.
    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="technical@vertere.local", password="s3nhaForte!")
    denied = await client.post(link_url, json={"clinic_id": clinic_id, "primary": False})
    assert denied.status_code == 403
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    # Desvincular libera o autônomo; a última clínica de um não autônomo conflita.
    unlinked = await client.delete(f"{link_url}/{clinic_id}")
    assert unlinked.status_code == 204
    assert (await client.get(f"/api/v1/veterinarians/{veterinarian_id}")).json()["clinics"] == []

    employed_id = await _create_veterinarian(
        client,
        name="Eberton Henrique",
        crmv="CRMV-SC 08915",
        is_autonomous=False,
        clinic_ids=[clinic_id],
    )
    last = await client.delete(f"/api/v1/veterinarians/{employed_id}/clinics/{clinic_id}")
    assert last.status_code == 409
    kept = await client.get(f"/api/v1/veterinarians/{employed_id}")
    assert len(kept.json()["clinics"]) == 1


async def test_clinic_actor_only_sees_veterinarians_and_links_of_own_clinic(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_admin(client, session_factory)
    own_clinic_id = await _create_clinic(client, "Propria")
    other_clinic_id = await _create_clinic(client, "Outra")
    own_vet_id = await _create_veterinarian(
        client,
        name="Vet Propria",
        crmv="CRMV-SC 00001",
        is_autonomous=False,
        clinic_ids=[own_clinic_id],
    )
    foreign_vet_id = await _create_veterinarian(
        client,
        name="Vet Outra",
        crmv="CRMV-SC 00002",
        is_autonomous=False,
        clinic_ids=[other_clinic_id],
    )
    shared_vet_id = await _create_veterinarian(
        client,
        name="Vet Compartilhada",
        crmv="CRMV-SC 00003",
        is_autonomous=False,
        clinic_ids=[own_clinic_id, other_clinic_id],
    )
    clinic_user = _create_user(
        session_factory,
        email="clinic-scope@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_CLINIC_ADMIN,
    )
    with session_factory() as session:
        now = datetime.now(UTC)
        session.add(
            ClinicMembershipModel(
                id=uuid4(),
                user_id=clinic_user.id,
                clinic_id=UUID(own_clinic_id),
                is_active=True,
                granted_at=now,
            )
        )
        for code in ("veterinarians.read", "veterinarians.manage", "clinics.read"):
            permission = session.query(PermissionModel).filter_by(code=code).one()
            session.add(
                RolePermissionModel(
                    role_id=ROLE_CLINIC_ADMIN, permission_id=permission.id, granted_at=now
                )
            )
        session.commit()
    client.cookies.clear()
    await _login(client, email="clinic-scope@vertere.local", password="s3nhaForte!")

    own = await client.get(f"/api/v1/veterinarians/{own_vet_id}")
    assert own.status_code == 200
    foreign = await client.get(f"/api/v1/veterinarians/{foreign_vet_id}")
    assert foreign.status_code == 404
    foreign_update = await client.patch(
        f"/api/v1/veterinarians/{foreign_vet_id}",
        json={
            "name": "Alterado",
            "crmv": "CRMV-SC 00002",
            "is_autonomous": False,
            "status": "ACTIVE",
            "expected_row_version": 1,
        },
    )
    assert foreign_update.status_code == 404
    shared = await client.get(f"/api/v1/veterinarians/{shared_vet_id}")
    assert shared.status_code == 200
    assert [item["clinic_id"] for item in shared.json()["clinics"]] == [own_clinic_id]
    other_clinic_vets = await client.get(f"/api/v1/clinics/{other_clinic_id}")
    assert other_clinic_vets.status_code == 404
