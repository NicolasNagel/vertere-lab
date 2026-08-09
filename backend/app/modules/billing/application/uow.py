"""Transactional boundary required by billing application handlers."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.billing.domain.repositories import (
    ClosureCandidateLockRepository,
    MonthlyClosureRepository,
)
from app.modules.clinics.domain.repositories import ClinicRepository
from app.shared.idempotency.domain.repositories import IdempotencyRecordRepository
from app.shared.outbox.domain.repositories import OutboxEventRepository


class BillingUnitOfWork(Protocol):
    @property
    def clinics(self) -> ClinicRepository: ...
    @property
    def candidates(self) -> ClosureCandidateLockRepository: ...
    @property
    def closures(self) -> MonthlyClosureRepository: ...
    @property
    def audit(self) -> AuditLogWriter: ...
    @property
    def outbox(self) -> OutboxEventRepository: ...
    @property
    def idempotency_records(self) -> IdempotencyRecordRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...
