"""SQLAlchemy clinic-directory unit of work."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork


class SqlAlchemyClinicDirectoryUnitOfWork:
    def __init__(self, base: SqlAlchemyUnitOfWork) -> None:
        self._base = base

    def __enter__(self) -> Self:
        self._base.__enter__()
        session = self._base.session
        self.clinics = SqlAlchemyClinicRepository(session)
        self.veterinarians = SqlAlchemyVeterinarianRepository(session)
        self.links = SqlAlchemyVeterinarianClinicLinkRepository(session)
        self.audit = SqlAlchemyAuditLogWriter(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._base.__exit__(exc_type, exc, traceback)

    def commit(self) -> None:
        self._base.commit()
