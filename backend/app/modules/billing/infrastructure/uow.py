"""SQLAlchemy adapter for the period closure unit of work."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.billing.infrastructure.repositories import (
    SqlAlchemyClosurePreviewRepository,
    SqlAlchemyMonthlyClosureRepository,
)
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.shared.idempotency.infrastructure.repositories import (
    SqlAlchemyIdempotencyRecordRepository,
)
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork
from app.shared.outbox.infrastructure.repositories import SqlAlchemyOutboxEventRepository


class SqlAlchemyBillingUnitOfWork:
    def __init__(self, base: SqlAlchemyUnitOfWork) -> None:
        self._base = base

    def __enter__(self) -> Self:
        self._base.__enter__()
        session = self._base.session
        self.clinics = SqlAlchemyClinicRepository(session)
        self.candidates = SqlAlchemyClosurePreviewRepository(session)
        self.closures = SqlAlchemyMonthlyClosureRepository(session)
        self.audit = SqlAlchemyAuditLogWriter(session)
        self.outbox = SqlAlchemyOutboxEventRepository(session)
        self.idempotency_records = SqlAlchemyIdempotencyRecordRepository(session)
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
