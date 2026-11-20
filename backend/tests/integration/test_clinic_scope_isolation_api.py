"""Integração com PostgreSQL real: um usuário de escopo CLÍNICA nunca enxerga nem altera usuários
ou veterinários fora das suas clínicas.

QA 2026-11-19 (fatia 6), com um perfil de clínica que tinha `users.*`: o usuário da clínica A listava
todos os usuários, desativava/mudava o papel de usuários da clínica B e do laboratório, vinculava a si
um veterinário da clínica B (e então o lia) e criava veterinário já vinculado à clínica B.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    RoleModel,
    RolePermissionModel,
    UserModel,
)
from app.modules.identity.infrastructure.seed import (
    ROLE_CLINIC_ADMIN,
    ROLE_LAB_ADMIN,
    ROLE_RECEPTION,
)

pytestmark = pytest.mark.integration

PASSWORD = "s3nhaForte!"
CLINIC_PERMISSIONS = (
    "users.read",
    "users.create",
    "users.deactivate",
    "users.activate",
    "roles.assign",
    "veterinarians.read",
    "veterinarians.manage",
    "clinics.read",
)


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
    session_factory: sessionmaker[Session], *, email: str, role_id: UUID, clinic_ids: list[UUID]
) -> UUID:
    with session_factory() as session:
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email=email,
            full_name=email,
            password_hash=hash_password(PASSWORD),
            is_active=True,
            role_id=role_id,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        if clinic_ids:
            for clinic_id in clinic_ids:
                session.add(
                    ClinicMembershipModel(
                        id=uuid4(),
                        user_id=user.id,
                        clinic_id=clinic_id,
                        is_active=True,
                        granted_at=now,
                    )
                )
        else:
            session.add(
                LabMembershipModel(id=uuid4(), user_id=user.id, is_active=True, granted_at=now)
            )
        session.commit()
        return user.id


def _grant_clinic_role_permissions(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        now = datetime.now(UTC)
        for code in CLINIC_PERMISSIONS:
            permission = session.query(PermissionModel).filter_by(code=code).one()
            exists = (
                session.query(RolePermissionModel)
                .filter_by(role_id=ROLE_CLINIC_ADMIN, permission_id=permission.id)
                .first()
            )
            if exists is None:
                session.add(
                    RolePermissionModel(
                        role_id=ROLE_CLINIC_ADMIN, permission_id=permission.id, granted_at=now
                    )
                )
        session.commit()


async def _login(client: httpx.AsyncClient, email: str) -> None:
    client.cookies.clear()
    response = await client.post(
        "/api/v1/auth/login", json={"login": email, "password": PASSWORD, "remember_me": False}
    )
    assert response.status_code == 200


async def _clinic(client: httpx.AsyncClient, name: str) -> UUID:
    response = await client.post("/api/v1/clinics", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["id"])


async def _vet(client: httpx.AsyncClient, crmv: str, clinic_ids: list[UUID]) -> str:
    response = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": f"Vet {crmv}",
            "crmv": crmv,
            "is_autonomous": False,
            "clinic_ids": [str(c) for c in clinic_ids],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_a_clinic_user_cannot_list_or_change_users_outside_its_clinic(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _grant_clinic_role_permissions(session_factory)
    _create_user(
        session_factory, email="lab-admin@vertere.local", role_id=ROLE_LAB_ADMIN, clinic_ids=[]
    )
    await _login(client, "lab-admin@vertere.local")
    clinic_a = await _clinic(client, "Clínica A")
    clinic_b = await _clinic(client, "Clínica B")
    lab_user = _create_user(
        session_factory, email="lab-recep@vertere.local", role_id=ROLE_RECEPTION, clinic_ids=[]
    )
    user_a = _create_user(
        session_factory,
        email="user-a@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a],
    )
    colleague_a = _create_user(
        session_factory,
        email="colleague-a@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a],
    )
    user_b = _create_user(
        session_factory,
        email="user-b@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_b],
    )
    shared = _create_user(
        session_factory,
        email="shared@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a, clinic_b],
    )

    await _login(client, "user-a@vertere.local")

    listed = await client.get("/api/v1/users", params={"page_size": 100})
    assert listed.status_code == 200
    emails = {item["email"] for item in listed.json()["items"]}
    assert emails == {"user-a@vertere.local", "colleague-a@vertere.local"}
    # search and the total never reveal the others either
    searched = await client.get("/api/v1/users", params={"search": "user-b"})
    assert searched.json()["total"] == 0

    for outsider in (user_b, lab_user, shared, uuid4()):
        for action in ("deactivate", "activate"):
            response = await client.patch(f"/api/v1/users/{outsider}/{action}")
            assert response.status_code == 404, (outsider, action)
        access = await client.patch(
            f"/api/v1/users/{outsider}/access",
            json={
                "role_id": str(ROLE_CLINIC_ADMIN),
                "clinic_ids": [str(clinic_a)],
                "expected_row_version": 1,
            },
        )
        assert access.status_code == 404, outsider
        role = await client.patch(
            f"/api/v1/users/{outsider}/role", json={"role_id": str(ROLE_LAB_ADMIN)}
        )
        assert role.status_code in (403, 404), outsider

    # a clinic actor never hands out laboratory roles, not even to its own colleague
    promote = await client.patch(
        f"/api/v1/users/{colleague_a}/role", json={"role_id": str(ROLE_LAB_ADMIN)}
    )
    assert promote.status_code == 403
    # and acting on a user of its own clinic still works
    own = await client.patch(f"/api/v1/users/{colleague_a}/deactivate")
    assert own.status_code == 200

    with session_factory() as session:
        rows = session.execute(
            text(
                "SELECT email, is_active, role_id FROM users WHERE email IN "
                "('user-b@vertere.local','lab-recep@vertere.local','shared@vertere.local')"
            )
        ).all()
        assert all(row.is_active for row in rows)
        assert {row.role_id for row in rows} == {ROLE_CLINIC_ADMIN, ROLE_RECEPTION}
    assert user_a != colleague_a  # sanity: the actor and its colleague are different users


async def test_a_clinic_user_cannot_pull_in_or_create_veterinarians_for_another_clinic(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _grant_clinic_role_permissions(session_factory)
    _create_user(
        session_factory, email="lab-admin@vertere.local", role_id=ROLE_LAB_ADMIN, clinic_ids=[]
    )
    await _login(client, "lab-admin@vertere.local")
    clinic_a = await _clinic(client, "Clínica A")
    clinic_b = await _clinic(client, "Clínica B")
    vet_of_b = await _vet(client, "CRMV-SC 70001", [clinic_b])
    _create_user(
        session_factory,
        email="user-a@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a],
    )

    await _login(client, "user-a@vertere.local")

    assert (await client.get(f"/api/v1/veterinarians/{vet_of_b}")).status_code == 404
    link = await client.post(
        f"/api/v1/veterinarians/{vet_of_b}/clinics",
        json={"clinic_id": str(clinic_a), "primary": False, "reason": "Quero ver"},
    )
    assert link.status_code == 404
    unlink = await client.request(
        "DELETE",
        f"/api/v1/veterinarians/{vet_of_b}/clinics/{clinic_b}",
        params={"reason": "Tentativa"},
    )
    assert unlink.status_code == 404
    # the veterinarian stays invisible: the link above must not have been created
    assert (await client.get(f"/api/v1/veterinarians/{vet_of_b}")).status_code == 404

    created = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": "Vet Intrusa",
            "crmv": "CRMV-SC 70002",
            "is_autonomous": False,
            "clinic_ids": [str(clinic_b)],
        },
    )
    assert created.status_code == 404
    with session_factory() as session:
        links = session.execute(
            text("SELECT count(*) FROM veterinarian_clinics WHERE clinic_id = :c"),
            {"c": clinic_a},
        ).scalar_one()
        intruder = session.execute(
            text("SELECT count(*) FROM veterinarians WHERE crmv = 'CRMV-SC 70002'")
        ).scalar_one()
    assert (links, intruder) == (0, 0)

    # its own clinic keeps working
    own = await client.post(
        "/api/v1/veterinarians",
        json={
            "name": "Vet da A",
            "crmv": "CRMV-SC 70003",
            "is_autonomous": False,
            "clinic_ids": [str(clinic_a)],
        },
    )
    assert own.status_code == 201


async def test_a_clinic_user_cannot_escalate_roles_or_manage_permission_profiles(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Auditor: scope checks alone let a clinic actor give itself a stronger clinic role, and the
    permission-profile endpoints had no scope veto for it."""
    _grant_clinic_role_permissions(session_factory)
    manage = ("roles.manage", "roles.read", "permissions.read")
    with session_factory() as session:
        now = datetime.now(UTC)
        for code in manage:
            permission = session.query(PermissionModel).filter_by(code=code).one()
            if (
                session.query(RolePermissionModel)
                .filter_by(role_id=ROLE_CLINIC_ADMIN, permission_id=permission.id)
                .first()
                is None
            ):
                session.add(
                    RolePermissionModel(
                        role_id=ROLE_CLINIC_ADMIN, permission_id=permission.id, granted_at=now
                    )
                )
        session.commit()
    _create_user(
        session_factory, email="lab-admin@vertere.local", role_id=ROLE_LAB_ADMIN, clinic_ids=[]
    )
    await _login(client, "lab-admin@vertere.local")
    clinic_a = await _clinic(client, "Clínica A")
    clinic_b = await _clinic(client, "Clínica B")
    # a clinic-scope profile that is STRONGER than the actor's (it holds closures.read)
    stronger_id = str(uuid4())
    with session_factory() as session:
        now = datetime.now(UTC)
        session.add(RoleModel(id=UUID(stronger_id), name="Clínica forte", scope="CLINIC"))
        session.flush()
        for code in ("closures.read", "patients.read"):
            permission = session.query(PermissionModel).filter_by(code=code).one()
            session.add(
                RolePermissionModel(
                    role_id=UUID(stronger_id), permission_id=permission.id, granted_at=now
                )
            )
        session.commit()
    actor = _create_user(
        session_factory,
        email="user-a@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a],
    )
    colleague = _create_user(
        session_factory,
        email="colleague-a@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a],
    )

    await _login(client, "user-a@vertere.local")

    # cannot grant a stronger clinic role, to itself or to a colleague, nor create a user with it
    for target in (actor, colleague):
        response = await client.patch(
            f"/api/v1/users/{target}/access",
            json={"role_id": stronger_id, "clinic_ids": [str(clinic_a)], "expected_row_version": 1},
        )
        assert response.status_code == 403, target
    created = await client.post(
        "/api/v1/users",
        json={
            "email": "new@vertere-qa.com",
            "full_name": "Novo",
            "role_id": stronger_id,
            "clinic_ids": [str(clinic_a)],
        },
    )
    assert created.status_code == 403
    # clinics outside the scope answer the same 404 whether they exist or not
    for foreign in (clinic_b, uuid4()):
        response = await client.patch(
            f"/api/v1/users/{colleague}/access",
            json={
                "role_id": str(ROLE_CLINIC_ADMIN),
                "clinic_ids": [str(foreign)],
                "expected_row_version": 1,
            },
        )
        assert response.status_code == 404, foreign

    # permission profiles are managed by the laboratory only
    forbidden_post = await client.post(
        "/api/v1/permission-profiles",
        json={"name": "Meu perfil", "scope": "LAB", "permission_codes": ["users.read"]},
    )
    forbidden_patch = await client.patch(
        f"/api/v1/permission-profiles/{ROLE_LAB_ADMIN}",
        json={"permission_codes": ["users.read"], "expected_row_version": 1},
    )
    assert forbidden_post.status_code == 403
    assert forbidden_patch.status_code in (403, 422)
    # it sees only clinic-scope profiles
    listed = await client.get("/api/v1/permission-profiles", params={"page_size": 100})
    assert listed.status_code == 200
    assert {item["scope"] for item in listed.json()["items"]} == {"CLINIC"}
    assert (await client.get(f"/api/v1/permission-profiles/{ROLE_LAB_ADMIN}")).status_code == 404

    with session_factory() as session:
        role_ids = {
            row[0]
            for row in session.execute(
                text("SELECT role_id FROM users WHERE email LIKE '%-a@vertere.local'")
            )
        }
    assert role_ids == {ROLE_CLINIC_ADMIN}


async def test_a_clinic_user_changes_only_veterinarians_that_belong_to_its_own_clinics(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _grant_clinic_role_permissions(session_factory)
    _create_user(
        session_factory, email="lab-admin@vertere.local", role_id=ROLE_LAB_ADMIN, clinic_ids=[]
    )
    await _login(client, "lab-admin@vertere.local")
    clinic_a = await _clinic(client, "Clínica A")
    clinic_b = await _clinic(client, "Clínica B")
    own = await _vet(client, "CRMV-SC 71001", [clinic_a])
    shared = await _vet(client, "CRMV-SC 71002", [clinic_a, clinic_b])
    created = await client.post(
        "/api/v1/veterinarians",
        json={"name": "Vet autônomo", "crmv": "CRMV-SC 71003", "is_autonomous": True},
    )
    assert created.status_code == 201, created.text
    unlinked = str(created.json()["id"])
    _create_user(
        session_factory,
        email="user-a@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a],
    )

    def body(crmv: str, *, autonomous: bool = False) -> dict[str, object]:
        return {
            "name": "Renomeado",
            "crmv": crmv,
            "is_autonomous": autonomous,
            "status": "ACTIVE",
            "reason": "Correção",
            "expected_row_version": 1,
        }

    await _login(client, "user-a@vertere.local")

    # shared with another clinic, or autonomous without links: visible, yet never changed by a clinic
    shared_url = f"/api/v1/veterinarians/{shared}"
    assert (await client.patch(shared_url, json=body("CRMV-SC 71002"))).status_code == 403
    assert (await client.post(f"{shared_url}/deactivate")).status_code == 403
    free_url = f"/api/v1/veterinarians/{unlinked}"
    assert (await client.get(free_url)).status_code == 200
    assert (
        await client.patch(free_url, json=body("CRMV-SC 71003", autonomous=True))
    ).status_code == 403
    assert (await client.post(f"{free_url}/deactivate")).status_code == 403

    # the clinic's own veterinarian can be edited, but not turned into an autonomous one
    own_url = f"/api/v1/veterinarians/{own}"
    assert (await client.patch(own_url, json=body("CRMV-SC 71001"))).status_code == 200
    current = (await client.get(own_url)).json()
    promoted = body("CRMV-SC 71001", autonomous=True)
    promoted["expected_row_version"] = current["row_version"]
    assert (await client.patch(own_url, json=promoted)).status_code == 403
    assert (await client.post(f"{own_url}/deactivate")).status_code == 200

    # the laboratory is not restricted
    await _login(client, "lab-admin@vertere.local")
    assert (
        await client.patch(f"/api/v1/veterinarians/{shared}", json=body("CRMV-SC 71002"))
    ).status_code == 200


async def test_a_clinic_user_cannot_adopt_an_unowned_autonomous_veterinarian(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _grant_clinic_role_permissions(session_factory)
    _create_user(
        session_factory, email="lab-admin@vertere.local", role_id=ROLE_LAB_ADMIN, clinic_ids=[]
    )
    await _login(client, "lab-admin@vertere.local")
    clinic_a = await _clinic(client, "Clínica A")
    created = await client.post(
        "/api/v1/veterinarians",
        json={"name": "Vet autônomo", "crmv": "CRMV-SC 72001", "is_autonomous": True},
    )
    assert created.status_code == 201, created.text
    free = str(created.json()["id"])
    _create_user(
        session_factory,
        email="user-a@vertere.local",
        role_id=ROLE_CLINIC_ADMIN,
        clinic_ids=[clinic_a],
    )

    await _login(client, "user-a@vertere.local")

    # linking would make the clinic its only owner, so it is refused and nothing is created
    link = await client.post(
        f"/api/v1/veterinarians/{free}/clinics",
        json={"clinic_id": str(clinic_a), "primary": False, "reason": "Adotar"},
    )
    assert link.status_code == 403
    batch = await client.patch(
        f"/api/v1/veterinarians/{free}/clinics",
        json={
            "add_clinic_ids": [str(clinic_a)],
            "remove_clinic_ids": [],
            "reason": "Adotar",
            "expected_row_version": 1,
        },
    )
    assert batch.status_code == 403, batch.text
    with session_factory() as session:
        count = session.execute(
            text("SELECT count(*) FROM veterinarian_clinics WHERE clinic_id = :c"),
            {"c": clinic_a},
        ).scalar_one()
    assert count == 0

    # a clinic user does not register autonomous veterinarians either
    autonomous = await client.post(
        "/api/v1/veterinarians",
        json={"name": "Outro", "crmv": "CRMV-SC 72002", "is_autonomous": True},
    )
    assert autonomous.status_code == 403
