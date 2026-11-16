"""Integração com PostgreSQL real (Testcontainers) — login, auditoria,
autorização e autoexclusão de controle, ponta a ponta via HTTPX/ASGI.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.audit.infrastructure.models import AuditLogModel
from app.modules.identity.infrastructure.models import (
    ClinicMembershipModel,
    LabMembershipModel,
    RoleModel,
    SessionModel,
    UserModel,
)
from app.modules.identity.infrastructure.seed import (
    ROLE_CLINIC_ADMIN,
    ROLE_LAB_ADMIN,
    ROLE_RECEPTION,
    ROLE_SUPER_ADMIN,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_user_data(session_factory: sessionmaker[Session]) -> None:
    # O container Postgres é module-scoped (mais rápido); sem isso, usuários
    # de um teste vazariam para o próximo e quebrariam premissas como "único
    # admin ativo" (rule: .claude/rules/08-testing.md — teste determinístico).
    # DELETE (não TRUNCATE ... CASCADE): TRUNCATE CASCADE arrastaria também
    # `role_permissions` (tem FK nullable para `users`), apagando o catálogo
    # seedado. DELETE respeita ON DELETE CASCADE/SET NULL já definidos nas FKs.
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM users"))
        session.commit()


def _create_user(
    session_factory: sessionmaker[Session],
    *,
    email: str,
    password: str,
    role_id: UUID,
    is_active: bool = True,
) -> UserModel:
    with session_factory() as session:
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email=email,
            full_name=email,
            password_hash=hash_password(password),
            is_active=is_active,
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


_PASSWORD = "s3nhaForte!"


async def _login(
    client: httpx.AsyncClient, email: str, password: str = _PASSWORD
) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": password, "remember_me": False},
    )


def _audit_entries(session_factory: sessionmaker[Session], action: str) -> list[AuditLogModel]:
    with session_factory() as session:
        return list(
            session.execute(select(AuditLogModel).where(AuditLogModel.action == action))
            .scalars()
            .all()
        )


async def test_login_rejects_invalid_credentials_and_accounts(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    _create_user(
        session_factory,
        email="inactive@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_RECEPTION,
        is_active=False,
    )
    _create_user(
        session_factory,
        email="clinic-client@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_CLINIC_ADMIN,
    )
    _create_user(
        session_factory,
        email="someone@vertere.local",
        password="correct-pass!",
        role_id=ROLE_RECEPTION,
    )
    _create_user(
        session_factory,
        email="brute-force-target@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_RECEPTION,
    )

    # Conta inativa é recusada mesmo com a senha certa; papel de clínica sem vínculo ativo
    # com uma clínica também não entra.
    inactive = await _login(client, "inactive@vertere.local")
    assert inactive.status_code == 401
    assert "vertere_session" not in inactive.cookies
    clinic_without_membership = await _login(client, "clinic-client@vertere.local")
    assert clinic_without_membership.status_code == 401
    assert "vertere_session" not in clinic_without_membership.cookies
    assert clinic_without_membership.json()["error"]["code"] == "UNAUTHENTICATED"

    # Usuário inexistente e senha errada são indistinguíveis para quem tenta.
    unknown = await _login(client, "ghost@vertere.local", "whatever")
    wrong_password = await _login(client, "someone@vertere.local", "wrong-pass!")
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json()["error"]["code"] == wrong_password.json()["error"]["code"]
    assert unknown.json()["error"]["message"] == wrong_password.json()["error"]["message"]

    # Payload acima do limite de tamanho é recusado antes de qualquer consulta.
    oversized = await _login(client, "a" * 100_000 + "@vertere.local", "whatever")
    assert oversized.status_code == 422

    # Achado de teste adversarial (ADR-007): 15 senhas erradas em paralelo, todas 401, sem
    # throttling. Agora, após repetidas falhas, até a senha certa recebe 429.
    attempts = [
        await _login(client, "brute-force-target@vertere.local", f"wrong-{index}")
        for index in range(5)
    ]
    assert all(attempt.status_code == 401 for attempt in attempts)
    assert (await _login(client, "brute-force-target@vertere.local")).status_code == 429


async def test_login_succeeds_audits_and_the_session_follows_account_changes(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        assert len(session.execute(select(RoleModel)).scalars().all()) == 9  # seed dos papéis

    reception = _create_user(
        session_factory, email="reception@vertere.local", password=_PASSWORD, role_id=ROLE_RECEPTION
    )
    response = await _login(client, "reception@vertere.local")
    assert response.status_code == 200
    assert "vertere_session" in response.cookies
    user = response.json()["user"]
    assert (user["email"], user["role_scope"], user["clinic_ids"], user["row_version"]) == (
        "reception@vertere.local",
        "LAB",
        [],
        1,
    )
    assert len(_audit_entries(session_factory, "auth.login_succeeded")) == 1

    # Revogar o vínculo com o laboratório invalida uma sessão que já existia.
    with session_factory() as session:
        membership = session.execute(
            select(LabMembershipModel).where(LabMembershipModel.user_id == reception.id)
        ).scalar_one()
        membership.is_active = False
        membership.revoked_at = datetime.now(UTC)
        session.commit()
    revoked = await client.get("/api/v1/auth/me")
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "UNAUTHENTICATED"

    # Papel de clínica entra quando há vínculo ativo com a clínica.
    _create_user(
        session_factory,
        email="admin-clinic-login@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_SUPER_ADMIN,
    )
    assert (await _login(client, "admin-clinic-login@vertere.local")).status_code == 200
    clinic_response = await client.post("/api/v1/clinics", json={"name": "Clinic Login QA"})
    assert clinic_response.status_code == 201
    clinic_id = UUID(clinic_response.json()["id"])
    clinic_user = _create_user(
        session_factory,
        email="clinic-active@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_CLINIC_ADMIN,
    )
    with session_factory() as session:
        session.add(
            ClinicMembershipModel(
                id=uuid4(),
                user_id=clinic_user.id,
                clinic_id=clinic_id,
                is_active=True,
                granted_at=datetime.now(UTC),
            )
        )
        session.commit()
    clinic_login = await _login(client, clinic_user.email)
    assert clinic_login.status_code == 200
    assert clinic_login.json()["user"]["role_scope"] == "CLINIC"
    assert clinic_login.json()["user"]["clinic_ids"] == [str(clinic_id)]


async def test_user_lifecycle_revokes_sessions_versions_changes_and_gates_by_permission(
    app: FastAPI, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="lab-admin@vertere.local", password=_PASSWORD, role_id=ROLE_LAB_ADMIN
    )
    _create_user(
        session_factory,
        email="powerless@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_RECEPTION,
    )
    target = _create_user(
        session_factory, email="target@vertere.local", password=_PASSWORD, role_id=ROLE_RECEPTION
    )

    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin_client,
        httpx.AsyncClient(transport=transport, base_url="http://test") as target_client,
        httpx.AsyncClient(transport=transport, base_url="http://test") as powerless_client,
        app.router.lifespan_context(app),
    ):
        assert (await _login(target_client, target.email)).status_code == 200
        assert (await target_client.get("/api/v1/auth/me")).status_code == 200
        assert (await _login(admin_client, "lab-admin@vertere.local")).status_code == 200
        assert (await _login(powerless_client, "powerless@vertere.local")).status_code == 200

        # Sem permissão, listar e ativar usuários é negado (autorização só no backend).
        assert (await powerless_client.get("/api/v1/users")).status_code == 403
        assert (
            await powerless_client.patch(f"/api/v1/users/{target.id}/activate")
        ).status_code == 403

        deactivated = await admin_client.patch(f"/api/v1/users/{target.id}/deactivate")
        assert deactivated.status_code == 200
        assert deactivated.json()["row_version"] == 2
        # O mesmo cookie de antes da desativação precisa parar de autenticar de imediato.
        assert (await target_client.get("/api/v1/auth/me")).status_code == 401

        activated = await admin_client.patch(f"/api/v1/users/{target.id}/activate")
        assert activated.status_code == 200
        assert activated.json()["is_active"] is True
        assert activated.json()["row_version"] == 3
        entries = _audit_entries(session_factory, "users.activated")
        assert [entry.entity_id for entry in entries] == [str(target.id)]
        with session_factory() as session:
            stored = session.get(UserModel, target.id)
            assert stored is not None
            assert stored.row_version == 3


async def test_role_changes_are_audited_and_guard_the_last_admin_and_input_size(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="sole-admin@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_LAB_ADMIN,
    )
    target = _create_user(
        session_factory, email="target@vertere.local", password=_PASSWORD, role_id=ROLE_RECEPTION
    )
    login = await _login(client, "sole-admin@vertere.local")
    admin_id = login.json()["user"]["id"]

    # O único admin não pode rebaixar a si mesmo.
    demote = await client.patch(
        f"/api/v1/users/{admin_id}/role", json={"role_id": str(ROLE_RECEPTION)}
    )
    assert demote.status_code == 409

    too_long = await client.post(
        "/api/v1/users",
        json={
            "email": "toolong@vertere.local",
            "full_name": "A" * 100_000,
            "role_id": str(ROLE_RECEPTION),
        },
    )
    assert too_long.status_code == 422

    promote = await client.patch(
        f"/api/v1/users/{target.id}/role", json={"role_id": str(ROLE_LAB_ADMIN)}
    )
    assert promote.status_code == 200
    entries = _audit_entries(session_factory, "users.role_changed")
    assert [entry.entity_id for entry in entries] == [str(target.id)]


async def test_permission_profiles_reject_concurrent_edits_and_self_lockout(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    # `roles.manage` (editar a regra de um perfil) é exclusivo do SUPER_ADMIN desde
    # alembic/versions/0032_restrict_roles_manage_to_super_admin.py.
    _create_user(
        session_factory,
        email="super-admin@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_SUPER_ADMIN,
    )
    assert (await _login(client, "super-admin@vertere.local")).status_code == 200

    profiles = await client.get("/api/v1/permission-profiles")
    reception = next(item for item in profiles.json()["items"] if item["name"] == "RECEPTION")

    # Duas requisições realmente paralelas (rules/08-testing.md) leem o mesmo `row_version`:
    # só uma vence, a outra recebe 409 — nunca "last write wins" silencioso.
    responses = await asyncio.gather(
        client.patch(
            f"/api/v1/permission-profiles/{reception['id']}",
            json={
                "permissions": ["clinics.read", "clinics.manage"],
                "expected_row_version": reception["row_version"],
            },
        ),
        client.patch(
            f"/api/v1/permission-profiles/{reception['id']}",
            json={
                "permissions": ["patients.read"],
                "expected_row_version": reception["row_version"],
            },
        ),
    )
    assert sorted(response.status_code for response in responses) == [200, 409]

    # ADR-007: o único SUPER_ADMIN não pode remover `roles.manage` do próprio perfil (travaria
    # o sistema sem volta pela UI/API) e o perfil segue intacto.
    own = (await client.get(f"/api/v1/permission-profiles/{ROLE_SUPER_ADMIN}")).json()
    without_roles_manage = [code for code in own["permissions"] if code != "roles.manage"]
    strip = await client.patch(
        f"/api/v1/permission-profiles/{ROLE_SUPER_ADMIN}",
        json={"permissions": without_roles_manage, "expected_row_version": own["row_version"]},
    )
    assert strip.status_code == 409
    unchanged = await client.get(f"/api/v1/permission-profiles/{ROLE_SUPER_ADMIN}")
    assert "roles.manage" in unchanged.json()["permissions"]

    # `attendances.view_prices` é exclusivo de papel GLOBAL: nem o SUPER_ADMIN a concede à
    # Recepção (papel LAB), e o perfil segue sem ela.
    current = (await client.get(f"/api/v1/permission-profiles/{ROLE_RECEPTION}")).json()
    grant = await client.patch(
        f"/api/v1/permission-profiles/{ROLE_RECEPTION}",
        json={
            "permissions": [*current["permissions"], "attendances.view_prices"],
            "expected_row_version": current["row_version"],
        },
    )
    assert grant.status_code == 422
    after = await client.get(f"/api/v1/permission-profiles/{ROLE_RECEPTION}")
    assert "attendances.view_prices" not in after.json()["permissions"]


async def test_update_user_access_is_versioned_atomic_and_revokes_sessions(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="admin-access@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_SUPER_ADMIN,
    )
    target = _create_user(
        session_factory,
        email="target-access@vertere.local",
        password=_PASSWORD,
        role_id=ROLE_RECEPTION,
    )
    assert (await _login(client, target.email)).status_code == 200
    assert (await _login(client, "admin-access@vertere.local")).status_code == 200

    response = await client.patch(
        f"/api/v1/users/{target.id}/access",
        json={"role_id": str(ROLE_LAB_ADMIN), "clinic_ids": [], "expected_row_version": 1},
    )
    assert response.status_code == 200
    assert response.json()["role_id"] == str(ROLE_LAB_ADMIN)
    assert response.json()["row_version"] == 2

    stale = await client.patch(
        f"/api/v1/users/{target.id}/access",
        json={"role_id": str(ROLE_RECEPTION), "clinic_ids": [], "expected_row_version": 1},
    )
    assert stale.status_code == 409

    with session_factory() as session:
        stored = session.get(UserModel, target.id)
        assert stored is not None
        assert (stored.role_id, stored.row_version) == (ROLE_LAB_ADMIN, 2)
        active_sessions = (
            session.execute(
                select(SessionModel).where(
                    SessionModel.user_id == target.id, SessionModel.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        assert active_sessions == []
        audit = session.execute(
            select(AuditLogModel).where(
                AuditLogModel.action == "users.access_changed",
                AuditLogModel.entity_id == str(target.id),
            )
        ).scalar_one()
        assert audit.before_state is not None
        assert audit.after_state is not None
        assert audit.before_state["role_id"] == str(ROLE_RECEPTION)
        assert audit.after_state["role_id"] == str(ROLE_LAB_ADMIN)
