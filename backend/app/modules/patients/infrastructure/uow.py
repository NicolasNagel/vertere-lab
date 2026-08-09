from __future__ import annotations

from types import TracebackType
from typing import Self

from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.patients.infrastructure.repositories import (
    SqlAlchemyPatientRepository,
    SqlAlchemySpeciesRepository,
)
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork


class SqlAlchemyPatientUnitOfWork:
    def __init__(self, base: SqlAlchemyUnitOfWork) -> None:
        self._base = base

    def __enter__(self) -> Self:
        self._base.__enter__()
        s = self._base.session
        self.patients = SqlAlchemyPatientRepository(s)
        self.species = SqlAlchemySpeciesRepository(s)
        self.clinics = SqlAlchemyClinicRepository(s)
        self.audit = SqlAlchemyAuditLogWriter(s)
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
