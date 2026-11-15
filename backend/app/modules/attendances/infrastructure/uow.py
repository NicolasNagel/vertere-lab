"""SQLAlchemy adapter for the attendance confirmation unit of work."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from app.modules.attendances.infrastructure.repositories import (
    SqlAlchemyAttendanceRepository,
    SqlAlchemyAttendanceSequenceRepository,
    SqlAlchemyClinicFeeRuleRepository,
    SqlAlchemyOnCallFeeSettingRepository,
    SqlAlchemyUrgencyFeeSettingRepository,
)
from app.modules.audit.infrastructure.repositories import SqlAlchemyAuditLogWriter
from app.modules.billing.application.settle_attendance_correction import (
    AttendanceCorrectionSettlement,
)
from app.modules.billing.infrastructure.repositories import SqlAlchemyMonthlyClosureRepository
from app.modules.catalog.infrastructure.repositories import SqlAlchemyExamRepository
from app.modules.clinics.infrastructure.repositories import SqlAlchemyClinicRepository
from app.modules.patients.infrastructure.repositories import SqlAlchemyPatientRepository
from app.modules.veterinarian_clinics.infrastructure.repositories import (
    SqlAlchemyVeterinarianClinicLinkRepository,
)
from app.modules.veterinarians.infrastructure.repositories import (
    SqlAlchemyVeterinarianRepository,
)
from app.shared.idempotency.infrastructure.repositories import (
    SqlAlchemyIdempotencyRecordRepository,
)
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.uow import SqlAlchemyUnitOfWork
from app.shared.outbox.infrastructure.repositories import SqlAlchemyOutboxEventRepository


class SqlAlchemyAttendanceUnitOfWork:
    def __init__(self, base: SqlAlchemyUnitOfWork) -> None:
        self._base = base

    def __enter__(self) -> Self:
        self._base.__enter__()
        session = self._base.session
        self.attendances = SqlAlchemyAttendanceRepository(session)
        self.attendance_sequences = SqlAlchemyAttendanceSequenceRepository(session)
        self.clinics = SqlAlchemyClinicRepository(session)
        self.veterinarians = SqlAlchemyVeterinarianRepository(session)
        self.veterinarian_clinics = SqlAlchemyVeterinarianClinicLinkRepository(session)
        self.patients = SqlAlchemyPatientRepository(session)
        self.exams = SqlAlchemyExamRepository(session)
        self.on_call_fees = SqlAlchemyOnCallFeeSettingRepository(session)
        self.urgency_fee = SqlAlchemyUrgencyFeeSettingRepository(session)
        self.clinic_fee_rules = SqlAlchemyClinicFeeRuleRepository(session)
        self.audit = SqlAlchemyAuditLogWriter(session)
        self.closure_settlement = AttendanceCorrectionSettlement(
            closures=SqlAlchemyMonthlyClosureRepository(session),
            audit=self.audit,
            outbox=SqlAlchemyOutboxEventRepository(session),
            clock=SystemClock(),
        )
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
