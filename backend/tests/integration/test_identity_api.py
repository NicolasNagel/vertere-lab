"""Integração com PostgreSQL real (Testcontainers) — login, auditoria,
autorização e autoexclusão de controle, ponta a ponta via HTTPX/ASGI.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.modules.audit.infrastructure.models import AuditLogModel
from app.modules.identity.infrastructure.models import LabMembershipModel, RoleModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_RECEPTION
from app.shared.infrastructure.database import build_engine, build_session_factory

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="module", autouse=True)
def _migrated_schema(postgres_url: str, monkeypatch_module: pytest.MonkeyPatch) -> None:
    monkeypatch_module.setenv("DATABASE_URL", postgres_url)
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "backend" / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="module")
def monkeypatch_module() -> Iterator[pytest.MonkeyPatch]:
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture
def session_factory(postgres_url: str) -> Iterator[sessionmaker[Session]]:
    engine = build_engine(postgres_url)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_user_data(session_factory: sessionmaker[Session]) -> None:
    # O container Postgres é module-scoped (mais rápido); sem isso, usuários
    # de um teste vazariam para o próximo e quebrariam premissas como "único
    # admin ativo" (rule: .claude/rules/testing.md — teste determinístico).
    # DELETE (não TRUNCATE ... CASCADE): TRUNCATE CASCADE arrastaria também
    # `role_permissions` (tem FK nullable para `users`), apagando o catálogo
    # seedado. DELETE respeita ON DELETE CASCADE/SET NULL já definidos nas FKs.
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM users"))
        session.commit()


@pytest.fixture
def settings(postgres_url: str) -> Settings:
    return Settings(
        env="test",
        log_level="WARNING",
        database_url=SecretStr(postgres_url),
        session_cookie_secure=False,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as async_client,
        app.router.lifespan_context(app),
    ):
        yield async_client


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


def test_seed_creates_expected_roles_and_permissions(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        role_count = len(session.execute(select(RoleModel)).scalars().all())
    assert role_count == 9


async def test_login_active_user_succeeds_and_audits(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="reception@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"login": "reception@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )

    assert response.status_code == 200
    assert "vertere_session" in response.cookies
    body = response.json()
    assert body["user"]["email"] == "reception@vertere.local"

    with session_factory() as session:
        entries = (
            session.execute(
                select(AuditLogModel).where(AuditLogModel.action == "auth.login_succeeded")
            )
            .scalars()
            .all()
        )
    assert len(entries) == 1


async def test_login_inactive_user_is_rejected_after_password_matches(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="inactive@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
        is_active=False,
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"login": "inactive@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )

    assert response.status_code == 401
    assert "vertere_session" not in response.cookies


async def test_login_unknown_user_and_wrong_password_return_identical_response(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="someone@vertere.local",
        password="correct-pass!",
        role_id=ROLE_RECEPTION,
    )

    unknown_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "ghost@vertere.local", "password": "whatever", "remember_me": False},
    )
    wrong_password_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "someone@vertere.local", "password": "wrong-pass!", "remember_me": False},
    )

    assert unknown_response.status_code == wrong_password_response.status_code == 401
    unknown_error = unknown_response.json()["error"]
    wrong_password_error = wrong_password_response.json()["error"]
    assert unknown_error["code"] == wrong_password_error["code"]
    assert unknown_error["message"] == wrong_password_error["message"]


async def test_me_without_session_is_unauthenticated(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_users_list_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="powerless@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "powerless@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )
    assert login_response.status_code == 200

    response = await client.get("/api/v1/users")
    assert response.status_code == 403


async def test_role_change_is_audited(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="lab-admin@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_LAB_ADMIN,
    )
    target = _create_user(
        session_factory,
        email="target@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "lab-admin@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )
    assert login_response.status_code == 200

    response = await client.patch(
        f"/api/v1/users/{target.id}/role", json={"role_id": str(ROLE_LAB_ADMIN)}
    )

    assert response.status_code == 200
    with session_factory() as session:
        entries = (
            session.execute(
                select(AuditLogModel).where(AuditLogModel.action == "users.role_changed")
            )
            .scalars()
            .all()
        )
    assert len(entries) == 1
    assert entries[0].entity_id == str(target.id)


async def test_concurrent_permission_updates_on_the_same_profile_reject_the_loser(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="lab-admin3@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_LAB_ADMIN,
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "lab-admin3@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )
    assert login_response.status_code == 200

    profile_response = await client.get("/api/v1/permission-profiles")
    reception = next(
        item for item in profile_response.json()["items"] if item["name"] == "RECEPTION"
    )
    row_version = reception["row_version"]

    # Duas requisições disparadas de verdade em paralelo (asyncio.gather),
    # não sequenciais fingindo concorrência (rule: .claude/rules/testing.md)
    # — ambas leem o mesmo `row_version` e tentam gravar por cima uma da
    # outra. Só uma pode vencer; a perdedora precisa de 409, nunca um
    # "last write wins" silencioso.
    responses = await asyncio.gather(
        client.patch(
            f"/api/v1/permission-profiles/{reception['id']}",
            json={"permissions": ["clinics.read", "clinics.manage"], "expected_row_version": row_version},
        ),
        client.patch(
            f"/api/v1/permission-profiles/{reception['id']}",
            json={"permissions": ["patients.read"], "expected_row_version": row_version},
        ),
    )

    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 409]


async def test_deactivating_a_user_revokes_their_active_session(
    app: FastAPI, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="lab-admin2@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_LAB_ADMIN,
    )
    target = _create_user(
        session_factory,
        email="soon-revoked@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )

    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin_client,
        httpx.AsyncClient(transport=transport, base_url="http://test") as target_client,
        app.router.lifespan_context(app),
    ):
        target_login = await target_client.post(
            "/api/v1/auth/login",
            json={
                "login": "soon-revoked@vertere.local",
                "password": "s3nhaForte!",
                "remember_me": False,
            },
        )
        assert target_login.status_code == 200

        me_before = await target_client.get("/api/v1/auth/me")
        assert me_before.status_code == 200

        admin_login = await admin_client.post(
            "/api/v1/auth/login",
            json={"login": "lab-admin2@vertere.local", "password": "s3nhaForte!", "remember_me": False},
        )
        assert admin_login.status_code == 200

        deactivate_response = await admin_client.patch(f"/api/v1/users/{target.id}/deactivate")
        assert deactivate_response.status_code == 200

        # Mesmo cookie de sessão de antes da desativação — precisa parar de
        # autenticar imediatamente, não só no próximo login.
        me_after = await target_client.get("/api/v1/auth/me")
        assert me_after.status_code == 401


async def test_activate_user_reactivates_and_audits(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="lab-admin@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_LAB_ADMIN,
    )
    target = _create_user(
        session_factory,
        email="target@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
        is_active=False,
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "lab-admin@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )
    assert login_response.status_code == 200

    response = await client.patch(f"/api/v1/users/{target.id}/activate")

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    with session_factory() as session:
        entries = (
            session.execute(
                select(AuditLogModel).where(AuditLogModel.action == "users.activated")
            )
            .scalars()
            .all()
        )
    assert len(entries) == 1
    assert entries[0].entity_id == str(target.id)


async def test_activate_user_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="powerless@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
    )
    target = _create_user(
        session_factory,
        email="target2@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_RECEPTION,
        is_active=False,
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "powerless@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )
    assert login_response.status_code == 200

    response = await client.patch(f"/api/v1/users/{target.id}/activate")
    assert response.status_code == 403


async def test_only_admin_cannot_demote_themselves(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="sole-admin@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_LAB_ADMIN,
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"login": "sole-admin@vertere.local", "password": "s3nhaForte!", "remember_me": False},
    )
    admin_id = login_response.json()["user"]["id"]

    response = await client.patch(
        f"/api/v1/users/{admin_id}/role", json={"role_id": str(ROLE_RECEPTION)}
    )

    assert response.status_code == 409
