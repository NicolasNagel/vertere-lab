"""Alembic environment.

The database URL comes exclusively from DATABASE_URL — never hardcoded, so
credentials stay out of the repository. Metadata comes from the shared
declarative base so autogenerate sees every model.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine

from alembic import context

# Side-effect imports: every module's models must be imported at least once
# so their tables register on `Base.metadata` before autogenerate compares
# it against the database.
from app.modules.audit.infrastructure import models as audit_models  # noqa: F401
from app.modules.identity.infrastructure import models as identity_models  # noqa: F401
from app.shared.infrastructure.database import Base

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set to run migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
