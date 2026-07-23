"""Integração com PostgreSQL real via Testcontainers (requer Docker).

Valida o encanamento de conexão e o pipeline de migration em banco vazio —
antes da primeira migration de verdade existir.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.shared.infrastructure.database import build_engine, build_session_factory
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


def test_engine_connects_and_queries(postgres_url: str) -> None:
    engine = build_engine(postgres_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_unit_of_work_commits_and_rolls_back(postgres_url: str) -> None:
    engine = build_engine(postgres_url)
    try:
        factory = build_session_factory(engine)

        with SqlAlchemyUnitOfWork(factory) as uow:
            uow.session.execute(text("CREATE TABLE uow_probe (id INTEGER PRIMARY KEY)"))
            uow.session.execute(text("INSERT INTO uow_probe (id) VALUES (1)"))
            uow.commit()

        with pytest.raises(RuntimeError, match="boom"), SqlAlchemyUnitOfWork(factory) as uow:
            uow.session.execute(text("INSERT INTO uow_probe (id) VALUES (2)"))
            raise RuntimeError("boom")  # sair sem commit deve descartar o insert

        with SqlAlchemyUnitOfWork(factory) as uow:
            rows = uow.session.execute(text("SELECT id FROM uow_probe")).scalars().all()
        assert rows == [1]
    finally:
        engine.dispose()


def test_alembic_upgrade_head_runs_on_empty_database(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "backend" / "alembic"))

    command.upgrade(config, "head")

    engine = build_engine(postgres_url)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            table_names = inspector.get_table_names()
        # `uow_probe` vem de um teste anterior no mesmo módulo (container
        # reutilizado, escopo "module") — o schema real vem das migrations
        # de identidade/auditoria (0001/0002).
        assert set(table_names) <= {
            "alembic_version",
            "uow_probe",
            "roles",
            "permissions",
            "role_permissions",
            "users",
            "lab_memberships",
            "sessions",
            "audit_log",
        }
        assert "roles" in table_names
    finally:
        engine.dispose()
