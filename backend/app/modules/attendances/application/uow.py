"""Transactional boundary required by attendance application handlers."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.modules.attendances.application.closure_settlement import ClosureSettlement
from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    AttendanceSequenceRepository,
    ClinicFeeRuleRepository,
    OnCallFeeSettingRepository,
    UrgencyFeeSettingRepository,
)
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.idempotency.domain.repositories import IdempotencyRecordRepository


class AttendanceUnitOfWork(Protocol):
    @property
    def attendances(self) -> AttendanceRepository: ...
    @property
    def attendance_sequences(self) -> AttendanceSequenceRepository: ...
    @property
    def clinics(self) -> ClinicRepository: ...
    @property
    def veterinarians(self) -> VeterinarianRepository: ...
    @property
    def veterinarian_clinics(self) -> VeterinarianClinicLinkRepository: ...
    @property
    def patients(self) -> PatientRepository: ...
    @property
    def exams(self) -> ExamRepository: ...
    @property
    def on_call_fees(self) -> OnCallFeeSettingRepository: ...
    @property
    def urgency_fee(self) -> UrgencyFeeSettingRepository: ...
    @property
    def clinic_fee_rules(self) -> ClinicFeeRuleRepository: ...
    @property
    def closure_settlement(self) -> ClosureSettlement: ...
    @property
    def audit(self) -> AuditLogWriter: ...
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
