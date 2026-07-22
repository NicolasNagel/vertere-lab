"""FastAPI dependencies: session and unit of work, one per request."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork


def _session_factory(request: Request) -> sessionmaker[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    return factory


def get_session(request: Request) -> Iterator[Session]:
    session = _session_factory(request)()
    try:
        yield session
    finally:
        session.close()


def get_unit_of_work(request: Request) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(_session_factory(request))
