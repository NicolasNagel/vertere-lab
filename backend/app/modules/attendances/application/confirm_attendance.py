"""Confirm a DRAFT attendance: revalidate every referenced id, snapshot exam
pricing into items, derive protocol and billing competence, transition to
CONFIRMED.

Item validation and pricing snapshot is shared with the preview (dry-run)
use case via `attendance_items.py` — this module only adds what is
exclusive to an actual commit: protocol consumption, persistence and
auditing. `Idempotency-Key` handling lives one layer up, in
`api/routers.py` (`app/shared/idempotency`) — this use case stays unaware
of retries/replay, it only executes once per call.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.attendances.application.attendance_items import (
    AttendanceItemInput as ConfirmAttendanceItemInput,
)
from app.modules.attendances.application.attendance_items import (
    resolve_on_call_fee,
    validate_and_snapshot_items,
)
from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.domain.entities import AttendanceStatus
from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    AttendanceSequenceRepository,
    OnCallFeeSettingRepository,
)
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

__all__ = [
    "ConfirmAttendanceCommand",
    "ConfirmAttendanceItemInput",
    "ConfirmAttendanceUseCase",
]

_REQUIRED_PERMISSION = "attendances.update"


@dataclass(frozen=True, kw_only=True)
class ConfirmAttendanceCommand:
    actor: AuthenticatedUserDTO
    attendance_id: UUID
    items: list[ConfirmAttendanceItemInput]


class ConfirmAttendanceUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        attendance_sequences: AttendanceSequenceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinics: VeterinarianClinicLinkRepository,
        patients: PatientRepository,
        exams: ExamRepository,
        on_call_fees: OnCallFeeSettingRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._attendances = attendances
        self._attendance_sequences = attendance_sequences
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._veterinarian_clinics = veterinarian_clinics
        self._patients = patients
        self._exams = exams
        self._on_call_fees = on_call_fees
        self._audit = audit
        self._clock = clock

    def execute(self, command: ConfirmAttendanceCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(command.attendance_id)
        if attendance is None:
            raise NotFoundError("Atendimento não encontrado.")
        if attendance.status != AttendanceStatus.DRAFT:
            raise ValidationError("Atendimento não está em rascunho.")

        before_state = {"status": attendance.status.value}

        items = validate_and_snapshot_items(
            attendance=attendance,
            items=command.items,
            actor=command.actor,
            clinics=self._clinics,
            veterinarians=self._veterinarians,
            veterinarian_clinics=self._veterinarian_clinics,
            patients=self._patients,
            exams=self._exams,
        )

        now = self._clock.now()
        assert attendance.service_date is not None  # enforced by validate_and_snapshot_items
        protocol_year = attendance.service_date.year
        protocol_sequence = self._attendance_sequences.next_sequence(protocol_year)

        on_call_fee = resolve_on_call_fee(
            service_level=attendance.service_level, on_call_fees=self._on_call_fees
        )
        attendance.confirm(
            items=items,
            protocol_year=protocol_year,
            protocol_sequence=protocol_sequence,
            on_call_fee=on_call_fee,
            now=now,
            confirmed_by=command.actor.id,
        )
        self._attendances.update(attendance)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="attendances.confirmed",
                entity_type="attendance",
                entity_id=str(attendance.id),
                before_state=before_state,
                after_state={
                    "status": attendance.status.value,
                    "protocol_number": attendance.protocol_number,
                    "grand_total": str(attendance.grand_total),
                },
            )
        )

        return attendance_to_dto(attendance)
