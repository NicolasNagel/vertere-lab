"""Create an empty DRAFT AttendanceRecord.

Every referenced id is validated here — and must be revalidated again at
confirmation time (`.claude/rules/12-attendance.md`: "Todo ID é revalidado no
momento da confirmação, mesmo que já tenha sido validado ao selecionar").
This use case only covers the draft creation step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.application.party_validation import (
    validate_clinic_veterinarian_patient,
)
from app.modules.attendances.domain.entities import AttendanceRecord, AttendanceStatus
from app.modules.attendances.domain.repositories import AttendanceRepository
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "attendances.create"


@dataclass(frozen=True, kw_only=True)
class CreateAttendanceDraftCommand:
    actor: AuthenticatedUserDTO
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    service_date: date | None
    notes: str | None


class CreateAttendanceDraftUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinics: VeterinarianClinicLinkRepository,
        patients: PatientRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._attendances = attendances
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._veterinarian_clinics = veterinarian_clinics
        self._patients = patients
        self._audit = audit
        self._clock = clock

    def execute(self, command: CreateAttendanceDraftCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        validate_clinic_veterinarian_patient(
            clinic_id=command.clinic_id,
            veterinarian_id=command.veterinarian_id,
            patient_id=command.patient_id,
            clinics=self._clinics,
            veterinarians=self._veterinarians,
            veterinarian_clinics=self._veterinarian_clinics,
            patients=self._patients,
        )

        now = self._clock.now()
        attendance = AttendanceRecord(
            id=uuid4(),
            clinic_id=command.clinic_id,
            veterinarian_id=command.veterinarian_id,
            patient_id=command.patient_id,
            service_date=command.service_date,
            notes=command.notes,
            status=AttendanceStatus.DRAFT,
            created_by=command.actor.id,
            updated_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._attendances.add(attendance)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="attendances.draft_created",
                entity_type="attendance",
                entity_id=str(attendance.id),
                after_state={
                    "clinic_id": str(attendance.clinic_id),
                    "veterinarian_id": str(attendance.veterinarian_id),
                    "patient_id": str(attendance.patient_id),
                    "status": attendance.status.value,
                },
            )
        )

        return attendance_to_dto(attendance)
