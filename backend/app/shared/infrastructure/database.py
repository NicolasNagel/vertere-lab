"""Engine, session factory and declarative base.

Every constraint gets an explicit name via the naming convention — required
for reviewable Alembic migrations (see .claude/rules/database.md).
"""

from __future__ import annotations

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_engine(database_url: str) -> Engine:
    # pool_pre_ping: serverless/pooler connections can be silently dropped.
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay usable after the unit of work
    # commits, without lazily hitting a closed session.
    return sessionmaker(bind=engine, expire_on_commit=False)
