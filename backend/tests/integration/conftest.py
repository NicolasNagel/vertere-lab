"""Infraestrutura compartilhada dos testes de integração (PostgreSQL real).

Um único container Postgres sobe por sessão e o schema é migrado **uma vez** num banco
molde (`vertere_template`). Cada módulo de teste recebe um banco próprio clonado desse molde
(`CREATE DATABASE ... TEMPLATE`), então:

- o isolamento entre arquivos é o mesmo de antes (dado semeado alterado por um arquivo, como
  perfis ou taxas de plantão, nunca vaza para outro);
- o custo de subir container e rodar Alembic deixa de ser pago uma vez por arquivo.

Limpeza de dados *entre testes* continua sendo responsabilidade de cada arquivo (cada um
conhece as tabelas que toca), via a fixture autouse `_reset_data`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN
from app.shared.infrastructure.database import build_engine, build_session_factory

REPO_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATE_DATABASE = "vertere_template"


def _run_admin(admin_url: str, statement: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(statement))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def _template_database() -> Iterator[tuple[str, str]]:
    """Sobe o Postgres, migra `vertere_template` até o head e devolve (url admin, url molde)."""
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        admin_url = postgres.get_connection_url()
        template_url = make_url(admin_url).set(database=_TEMPLATE_DATABASE)
        _run_admin(admin_url, f'CREATE DATABASE "{_TEMPLATE_DATABASE}"')

        rendered_template_url = template_url.render_as_string(hide_password=False)
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("DATABASE_URL", rendered_template_url)
            config = Config()
            config.set_main_option("script_location", str(REPO_ROOT / "backend" / "alembic"))
            command.upgrade(config, "head")
        yield admin_url, rendered_template_url


@pytest.fixture(scope="module")
def postgres_url(
    request: pytest.FixtureRequest, _template_database: tuple[str, str]
) -> Iterator[str]:
    """Banco exclusivo do módulo, clonado do molde já migrado; exporta `DATABASE_URL`."""
    admin_url, _ = _template_database
    database = request.module.__name__.rsplit(".", 1)[-1]
    # O molde não pode ter conexões abertas durante a clonagem.
    _run_admin(
        admin_url,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{_TEMPLATE_DATABASE}'",
    )
    _run_admin(admin_url, f'CREATE DATABASE "{database}" TEMPLATE "{_TEMPLATE_DATABASE}"')
    url = make_url(admin_url).set(database=database).render_as_string(hide_password=False)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", url)
        yield url
    _run_admin(admin_url, f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')


@pytest.fixture
def session_factory(postgres_url: str) -> Iterator[sessionmaker[Session]]:
    engine = build_engine(postgres_url)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


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


@pytest.fixture
async def admin_client(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> httpx.AsyncClient:
    """`client` already logged in as a LAB_ADMIN (every module's tests may need one)."""
    now = datetime.now(UTC)
    with session_factory() as session:
        user = UserModel(
            id=uuid4(),
            email="shared-admin@vertere.local",
            full_name="Shared Admin",
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
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "login": "shared-admin@vertere.local",
            "password": "s3nhaForte!",
            "remember_me": False,
        },
    )
    assert response.status_code == 200
    return client
